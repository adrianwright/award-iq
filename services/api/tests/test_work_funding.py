from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import funding, main
from app.auth import AuthenticatedUser, require_api_user
from app.config import get_settings
from app.schemas import Source
from app.sources.fabric_funding import FUNDING_TABLES, FundingDataUnavailable
from app.sources import work_funding
from app.workiq import WorkIQAnswer, WorkIQDocument, WorkIQRetrieval, WorkIQTokenExchangeError

DOC = "DOC-FO117-TRACKER2"
URL = "https://contoso.sharepoint.com/sites/demo/Shared%20Documents/tracker.docx"


def _settings():
    return get_settings().model_copy(update={
        "USE_LIVE_WORK": True,
        "WORK_IQ_FUNDING_DOCUMENT_URLS": json.dumps({DOC: URL}),
    })


def _documents():
    return {
        row["document_id"]: row
        for row in funding._read_rows(get_settings().DATA_DIR, "source_documents")
        if row["source"] == "work" and row["notice_id"] == "FO-2026-117"
        and row["document_id"] != "DOC-FO117-TRACKER1"
    }


def _answer(url=URL):
    return WorkIQRetrieval(
        documents=(WorkIQDocument(
            citation_id="h1",
            markdown="Maria's match task remains open; the proposed review is not booked. [^h1]",
            url=url, sensitivity_label={},
        ),),
        duration_ms=42,
    )


def test_retrieval_uses_delegated_token_and_only_allowlisted_current_documents(monkeypatch):
    calls = []

    class Client:
        def __init__(self, _settings):
            pass

        def retrieve(self, **kwargs):
            calls.append(kwargs)
            return _answer()

    monkeypatch.setattr(work_funding, "WorkIQClient", Client)
    result = work_funding.retrieve_funding_work(
        _settings(), user_access_token="user-token", question="Who follows up?",
        notice_id="FO-2026-117", documents=_documents(),
    )
    assert calls[0]["user_assertion"] == "user-token"
    assert "FO-2026-117" in calls[0]["query"]
    assert calls[0]["document_urls"] == [URL]
    assert f"[{DOC}]" in result.answer
    assert "[^h1]" not in result.answer
    assert result.citations[0].refId == DOC
    assert result.citations[0].url == URL
    assert "not a verbatim excerpt" in result.citations[0].sourceType


@pytest.mark.parametrize("attribution_url", [None, "https://contoso.sharepoint.com/other.docx"])
def test_unattributed_or_out_of_scope_results_fail_closed(monkeypatch, attribution_url):
    class Client:
        def __init__(self, _settings):
            pass

        def retrieve(self, **kwargs):
            return _answer(attribution_url)

    monkeypatch.setattr(work_funding, "WorkIQClient", Client)
    with pytest.raises(FundingDataUnavailable, match="unverified or out-of-scope"):
        work_funding.retrieve_funding_work(
            _settings(), user_access_token="user-token", question="Who?",
            notice_id="FO-2026-117", documents=_documents(),
        )


def test_out_of_scope_result_fails_even_when_a_valid_document_is_also_returned(monkeypatch):
    class Client:
        def __init__(self, _settings):
            pass

        def retrieve(self, **kwargs):
            return WorkIQRetrieval(
                documents=(
                    *_answer().documents,
                    WorkIQDocument("h2", "Other content", "https://contoso.sharepoint.com/other", {}),
                ),
                duration_ms=1,
            )

    monkeypatch.setattr(work_funding, "WorkIQClient", Client)
    with pytest.raises(FundingDataUnavailable, match="unverified or out-of-scope"):
        work_funding.retrieve_funding_work(
            _settings(), user_access_token="user-token", question="Who?",
            notice_id="FO-2026-117", documents=_documents(),
        )


@pytest.mark.parametrize("returned_url,drive_id,item_id,accepted", [
    (URL.replace("%20", " ") + "?web=1", None, None, True),
    ("https://contoso.sharepoint.com/sites/demo/_layouts/15/Doc.aspx?sourcedoc=opaque", "drive-1", "item-1", True),
    ("https://contoso.sharepoint.com/sites/demo/_layouts/15/Doc.aspx?sourcedoc=opaque", None, None, False),
    ("https://contoso.sharepoint.com/sites/other/tracker.docx", None, None, True),
    (URL, "drive-1", "wrong-item", False),
    ("https://other.sharepoint.com/tracker.docx", "drive-1", "item-1", False),
    ("https://contoso.sharepoint.com/sites/demo/_layouts/15/Doc.aspx?file=TRACKER.docx", None, None, True),
    ("https://contoso.sharepoint.com/sites/demo/_layouts/15/Doc.aspx?file=unrelated.docx", None, None, False),
])
def test_source_matching_requires_verified_document_identity(
    monkeypatch, caplog, returned_url, drive_id, item_id, accepted,
):
    settings = _settings().model_copy(update={
        "WORK_IQ_FUNDING_DOCUMENT_IDENTITIES": json.dumps({
            DOC: {"webUrl": URL, "driveId": "drive-1", "itemId": "item-1"},
        }),
    })

    class Client:
        def __init__(self, _settings):
            pass

        def retrieve(self, **kwargs):
            return WorkIQRetrieval(
                (WorkIQDocument("h1", "Match task remains open. [^h1]", returned_url, {}, drive_id, item_id),),
                1,
            )

    monkeypatch.setattr(work_funding, "WorkIQClient", Client)
    if accepted:
        result = work_funding.retrieve_funding_work(
            settings, user_access_token="user-token", question="Who?",
            notice_id="FO-2026-117", documents=_documents(),
        )
        assert result.citations[0].url == returned_url
        assert result.citations[0].refId == DOC
    else:
        with pytest.raises(FundingDataUnavailable, match="unverified or out-of-scope"):
            work_funding.retrieve_funding_work(
                settings, user_access_token="user-token", question="Who?",
                notice_id="FO-2026-117", documents=_documents(),
            )
        assert "Work IQ source identity rejected" in caplog.text
    assert returned_url not in caplog.text
    assert "Match task remains open" not in caplog.text
    assert "user-token" not in caplog.text


def test_filename_metadata_matches_viewer_link_but_rejects_ambiguous_names(monkeypatch):
    class Client:
        def __init__(self, _settings):
            pass

        def retrieve(self, **kwargs):
            return WorkIQRetrieval((WorkIQDocument(
                "h1", "Match task remains open. [^h1]",
                "https://contoso.sharepoint.com/_layouts/15/Doc.aspx?sourcedoc=opaque",
                {}, title="tracker.docx",
            ),), 1)

    monkeypatch.setattr(work_funding, "WorkIQClient", Client)
    result = work_funding.retrieve_funding_work(
        _settings(), user_access_token="user-token", question="Who?",
        notice_id="FO-2026-117", documents=_documents(),
    )
    assert result.citations[0].refId == DOC
    assert "matched by filename" in result.citations[0].sourceType

    other_id = "DOC-FO117-HUDDLE"
    settings = _settings().model_copy(update={
        "WORK_IQ_FUNDING_DOCUMENT_URLS": json.dumps({
            DOC: URL, other_id: "https://contoso.sharepoint.com/another/tracker.docx",
        }),
    })
    with pytest.raises(FundingDataUnavailable, match="unverified or out-of-scope"):
        work_funding.retrieve_funding_work(
            settings, user_access_token="user-token", question="Who?",
            notice_id="FO-2026-117", documents=_documents(),
        )


def test_work_iq_failure_never_falls_back_to_packaged_content(monkeypatch):
    class Client:
        def __init__(self, _settings):
            pass

        def retrieve(self, **kwargs):
            raise WorkIQTokenExchangeError("consent required")

    monkeypatch.setattr(work_funding, "WorkIQClient", Client)
    with pytest.raises(FundingDataUnavailable, match="No packaged Work IQ fallback"):
        work_funding.retrieve_funding_work(
            _settings(), user_access_token="user-token", question="Who?",
            notice_id="FO-2026-117", documents=_documents(),
        )


def test_missing_user_token_or_current_document_fails_before_network():
    with pytest.raises(FundingDataUnavailable, match="delegated token"):
        work_funding.retrieve_funding_work(
            _settings(), user_access_token=None, question="Who?",
            notice_id="FO-2026-117", documents=_documents(),
        )
    with pytest.raises(FundingDataUnavailable, match="No current Work IQ demo documents"):
        work_funding.retrieve_funding_work(
            _settings(), user_access_token="user-token", question="Who?",
            notice_id="FO-2026-117", documents={},
        )


def test_progress_retains_completed_sources_when_work_retrieval_fails(monkeypatch):
    def fail(*args, **kwargs):
        raise FundingDataUnavailable("Work IQ returned no indexed documents")

    monkeypatch.setattr(funding, "retrieve_funding_work", fail)
    progress = []
    with pytest.raises(FundingDataUnavailable):
        funding.assess_funding(
            _settings(), "FO-2026-117", user_access_token="user-token",
            on_progress=progress.append,
        )
    assert [(item.source, item.status) for item in progress[:2]] == [
        (Source.FABRIC, "searching"), (Source.FABRIC, "retrieved"),
    ]
    for source, expected in [
        (Source.FOUNDRY, ["searching", "retrieved"]),
        (Source.WORK, ["searching", "failed"]),
        (Source.WEB, ["searching", "retrieved"]),
    ]:
        assert [item.status for item in progress if item.source == source] == expected


def test_independent_sources_overlap_after_fabric_scope_is_resolved(monkeypatch):
    import threading
    from app.sources.foundry_funding import FundingKnowledge

    barrier = threading.Barrier(3, timeout=5)
    original_citation = funding._citation
    scope_ready = threading.Event()
    settings = _settings().model_copy(update={"USE_LIVE_FOUNDRY": True})

    def foundry(settings, **kwargs):
        assert scope_ready.is_set()
        barrier.wait()
        return FundingKnowledge(
            "Current amendment", [
                original_citation(settings.DATA_DIR, document)
                for document in kwargs["documents"].values()
            ], "query", 1,
        )

    def work(settings, **kwargs):
        assert scope_ready.is_set()
        barrier.wait()
        return work_funding.FundingWork(
            "Match task remains open.", [
                original_citation(settings.DATA_DIR, document)
                for document in kwargs["documents"].values()
            ], "query", 1,
        )

    waited_for_web = False

    def citation(data_dir, document):
        nonlocal waited_for_web
        if document["source"] == "web" and not waited_for_web:
            waited_for_web = True
            assert scope_ready.is_set()
            barrier.wait()
        return original_citation(data_dir, document)

    def progress(update):
        if update.source == Source.FABRIC and update.status == "retrieved":
            scope_ready.set()

    monkeypatch.setattr(funding, "retrieve_funding_knowledge", foundry)
    monkeypatch.setattr(funding, "retrieve_funding_work", work)
    monkeypatch.setattr(funding, "_citation", citation)
    result = funding.assess_funding(
        settings, "FO-2026-117", user_access_token="user-token", on_progress=progress,
    )
    assert waited_for_web
    assert result.matchGap == 450_000
    assert result.submissionStatus == "Not submitted"


def test_stream_reports_only_the_actual_failed_source(monkeypatch):
    def fail(settings, question, *, on_progress, **kwargs):
        from app.funding import FundingSourceProgress
        on_progress(FundingSourceProgress(source=Source.FABRIC, status="searching"))
        on_progress(FundingSourceProgress(source=Source.FABRIC, status="retrieved", citations=["fabric-id"]))
        on_progress(FundingSourceProgress(source=Source.FOUNDRY, status="searching"))
        on_progress(FundingSourceProgress(source=Source.FOUNDRY, status="retrieved", citations=["foundry-id"]))
        on_progress(FundingSourceProgress(source=Source.WORK, status="searching"))
        raise FundingDataUnavailable("No indexed Work IQ evidence")

    monkeypatch.setattr(main, "assess_funding", fail)
    main.app.dependency_overrides[require_api_user] = lambda: None
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/funding/ask/stream", json={"question": "FO-2026-117"})
    finally:
        main.app.dependency_overrides.pop(require_api_user, None)
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    states = [(item["source"], item["status"]) for item in events if "source" in item]
    assert states == [
        ("fabric", "searching"), ("fabric", "retrieved"),
        ("foundry", "searching"), ("foundry", "retrieved"),
        ("work", "searching"), ("work", "failed"),
    ]
    assert events[-1] == {"message": "No indexed Work IQ evidence"}
    assert not any('"result":' in line for line in response.text.splitlines())


def test_stream_delivers_progress_before_the_assessment_finishes(monkeypatch):
    import asyncio
    import threading
    from app.funding import FundingSourceProgress
    from app.schemas import AskRequest

    release = threading.Event()
    result = funding.assess_funding(get_settings(), "FO-2026-117")

    def assess(settings, question, *, on_progress, **kwargs):
        on_progress(FundingSourceProgress(source=Source.FABRIC, status="searching"))
        assert release.wait(5), "The stream buffered progress until after assessment completion"
        return result

    monkeypatch.setattr(main, "assess_funding", assess)

    async def consume():
        response = await main.ask_funding_stream(AskRequest(question="FO-2026-117"), None)
        iterator = response.body_iterator
        assert (await anext(iterator))["event"] == "plan"
        try:
            event = await asyncio.wait_for(anext(iterator), timeout=3)
            assert event["event"] == "source_query"
            assert json.loads(event["data"])["source"] == "fabric"
        finally:
            release.set()
        remaining = [event async for event in iterator]
        assert remaining[-1]["event"] == "final"

    asyncio.run(consume())


def test_assessment_uses_live_work_evidence_without_reading_work_fixtures(monkeypatch):
    settings = _settings().model_copy(update={"USE_LIVE_FABRIC": True})
    rows = {name: funding._read_rows(settings.DATA_DIR, name) for name in FUNDING_TABLES}
    monkeypatch.setattr(funding, "read_funding_tables", lambda _: rows)
    original = funding._citation

    def citation(data_dir, document):
        assert document["source"] != "work"
        return original(data_dir, document)

    monkeypatch.setattr(funding, "_citation", citation)

    class Client:
        def __init__(self, _settings):
            pass

        def retrieve(self, **kwargs):
            assert kwargs["user_assertion"] == "user-token"
            return _answer()

    monkeypatch.setattr(work_funding, "WorkIQClient", Client)
    result = funding.assess_funding(settings, "FO-2026-117", user_access_token="user-token")

    assert result.workMode == "work_iq"
    assert result.matchGap == 450_000
    assert result.pursuitStatus == "Pursue - pending"
    work_sources = [item for item in result.evidence if item.source == Source.WORK]
    assert [item.refId for item in work_sources] == [DOC]
    assert any(item.heading == "Live Work IQ coordination context" for item in result.retrievalContext)
    assert not any(item.heading == "Live Work IQ coordination context" for item in result.rationale)
    assert "retrievalContext" not in result.model_dump()
    source = next(item for item in result.sourceMap if item["source"] == "work")
    assert source["citations"] == [DOC]
    assert source["durationMs"] == 42


def test_both_funding_endpoints_forward_signed_in_user_token(monkeypatch):
    user = AuthenticatedUser(
        access_token="forward-me", tenant_id="test", subject="test",
        scopes=frozenset({"access_as_user"}), claims={},
    )
    seen = []
    original = main.assess_funding

    def assess(settings, question, **kwargs):
        seen.append(kwargs["user_access_token"])
        return original(settings, question)

    monkeypatch.setattr(main, "assess_funding", assess)
    main.app.dependency_overrides[require_api_user] = lambda: user
    try:
        client = TestClient(main.app)
        assert client.post("/api/funding/ask", json={"question": "FO-2026-117"}).status_code == 200
        assert client.post("/api/funding/ask/stream", json={"question": "FO-2026-117"}).status_code == 200
    finally:
        main.app.dependency_overrides.pop(require_api_user, None)
    assert seen == ["forward-me", "forward-me"]


@pytest.mark.parametrize("response_text,expected_status", [
    ("AWARD_IQ_CONNECTED", 200),
    ("I cannot complete that check.", 503),
])
def test_work_iq_connection_check_forwards_user_and_requires_acknowledgment(
    monkeypatch, response_text, expected_status,
):
    class Client:
        def __init__(self, _settings):
            pass

        def ask(self, *, user_assertion, question):
            assert user_assertion == "test-user-token"
            assert "Do not search, read, summarize or change any workplace data" in question
            return WorkIQAnswer(
                text=response_text, task_id=None, context_id=None, duration_ms=42,
            )

    monkeypatch.setattr(main, "WorkIQClient", Client)
    response = TestClient(main.app).post("/api/workiq/check")
    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json()["status"] == "connected"
        assert "Document access is not yet verified" in response.json()["message"]


def test_work_iq_connection_check_reports_actual_exchange_failure(monkeypatch):
    class Client:
        def __init__(self, _settings):
            pass

        def ask(self, **kwargs):
            raise WorkIQTokenExchangeError("Work IQ OBO failed (invalid_grant)")

    monkeypatch.setattr(main, "WorkIQClient", Client)
    response = TestClient(main.app).post("/api/workiq/check")
    assert response.status_code == 503
    assert response.json()["detail"] == "Work IQ OBO failed (invalid_grant)"


def test_work_iq_connection_check_requires_sign_in_even_in_local_mode():
    main.app.dependency_overrides[require_api_user] = lambda: None
    try:
        response = TestClient(main.app).post("/api/workiq/check")
        assert response.status_code == 401
    finally:
        main.app.dependency_overrides.pop(require_api_user, None)


def test_document_verification_uses_live_work_only_for_the_explicit_request(monkeypatch):
    seen = []

    def assess(settings, question, **kwargs):
        assert settings.USE_LIVE_WORK
        assert kwargs["user_access_token"] == "test-user-token"
        seen.append(question)
        result = funding.assess_funding(get_settings(), question)
        return result.model_copy(update={"workMode": "work_iq"})

    monkeypatch.setattr(main, "assess_funding", assess)
    before = main.settings.USE_LIVE_WORK
    response = TestClient(main.app).post("/api/workiq/check?notice_id=FO-2026-117")
    assert response.status_code == 200
    assert response.json()["status"] == "verified"
    assert seen == ["FO-2026-117"]
    assert main.settings.USE_LIVE_WORK == before


def test_document_verification_does_not_report_success_after_retrieval_failure(monkeypatch):
    def assess(*args, **kwargs):
        raise FundingDataUnavailable("Work IQ returned no attributed demo evidence; no fallback was used.")

    monkeypatch.setattr(main, "assess_funding", assess)
    response = TestClient(main.app).post("/api/workiq/check?notice_id=FO-2026-117")
    assert response.status_code == 503
    assert "no attributed demo evidence" in response.json()["detail"]
