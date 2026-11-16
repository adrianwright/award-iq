from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest

from app import funding
from app.config import SettingsConfigurationError, get_settings
from app.schemas import Evidence, Source
from app.sources import foundry_funding as foundry
from app.sources.fabric_funding import FUNDING_TABLES, FundingDataUnavailable

DOCUMENT_ID = "DOC-FO117-AMD2"


def _documents():
    settings = get_settings()
    return {
        row["document_id"]: row
        for row in funding._read_rows(settings.DATA_DIR, "source_documents")
        if row["source"] == "foundry" and row["notice_id"] == "FO-2026-117"
        and row["document_id"] != "DOC-FO117-AMD1"
    }


def _mock_credential(monkeypatch):
    credential = MagicMock()
    credential.__enter__.return_value = credential
    credential.get_token.return_value.token = "test-token"
    monkeypatch.setattr(foundry, "_credential", lambda _: credential)
    return credential


def _retrieve(monkeypatch, response: dict, status: int = 200):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=response)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(foundry.httpx, "Client", lambda **_: client)
    _mock_credential(monkeypatch)
    settings = get_settings().model_copy(update={
        "SEARCH_ENDPOINT": "https://award-test.search.windows.net",
        "FOUNDRY_KB_NAME": "award-iq-funding-kb",
        "FOUNDRY_KS_NAME": "award-iq-funding-ks",
    })
    result = foundry.retrieve_funding_knowledge(
        settings, question="What changed?", notice_id="FO-2026-117",
        as_of=date(2026, 11, 16), documents=_documents(),
        controlling_document_id=DOCUMENT_ID,
    )
    return result, requests


def _retrieval_response():
    return {
        "response": [{"content": [{
            "type": "text", "text": "Current match is 25%; a signed partner letter is required [ref_id:0].",
        }]}],
        "references": [{
            "id": "0", "docKey": DOCUMENT_ID,
            "sourceData": {"id": DOCUMENT_ID, "content": "Live retrieved Amendment 2 body: 25% match."},
        }],
    }


def test_retrieval_scopes_notice_and_effective_version_and_uses_cloud_text(monkeypatch):
    result, requests = _retrieve(monkeypatch, _retrieval_response())

    assert result.citations[0].snippet == "Live retrieved Amendment 2 body: 25% match."
    assert result.citations[0].refId == DOCUMENT_ID
    assert f"[{DOCUMENT_ID}]" in result.answer
    payload = json.loads(requests[0].content)
    options = payload["knowledgeSourceParams"][0]
    assert "notice_id eq 'FO-2026-117'" in options["filterAddOn"]
    assert "effective_from le 2026-11-16T00:00:00Z" in options["filterAddOn"]
    assert "valid_until gt 2026-11-16T00:00:00Z" in options["filterAddOn"]
    assert options["includeReferenceSourceData"] is True
    assert options["failOnError"] is True


@pytest.mark.parametrize("failure", ["http", "partial", "no_refs", "other_notice", "missing_body", "unknown_citation"])
def test_retrieval_failures_never_substitute_packaged_documents(monkeypatch, failure):
    response = _retrieval_response()
    status = 200
    if failure == "http":
        status = 503
    elif failure == "partial":
        status = 206
    elif failure == "no_refs":
        response["references"] = []
    elif failure == "other_notice":
        response["references"][0]["sourceData"]["id"] = "DOC-FO204-TERMS"
    elif failure == "missing_body":
        response["references"][0]["sourceData"]["content"] = ""
    else:
        response["response"][0]["content"][0]["text"] = "Unsupported [ref_id:99]"
    with pytest.raises(FundingDataUnavailable):
        _retrieve(monkeypatch, response, status)


def _model_response(monkeypatch, assessment, *, text: str | None = None, refs=None):
    _mock_credential(monkeypatch)
    client = MagicMock()
    client.__enter__.return_value = client
    completion = client.chat.completions.create.return_value
    completion.model = "gpt-5.6-luna-2026-07-09"
    completion.id = "test-response"
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message.content = json.dumps({
        "answer": text or f"Pursue - pending; the gap is $450,000 [{DOCUMENT_ID}].",
        "bottomLine": "Human review required; no application has been submitted.",
        "evidenceRefs": refs or [DOCUMENT_ID],
    })
    completion.choices = [choice]
    monkeypatch.setattr(foundry, "OpenAI", lambda **_: client)
    settings = get_settings().model_copy(update={
        "FOUNDRY_ENDPOINT": "https://award-test.openai.azure.com",
        "MODEL_DEPLOYMENT": "award-iq-reasoning",
    })
    return foundry.synthesize_funding_answer(settings, assessment), client


def test_real_model_request_is_grounded_in_assessment_and_citation_schema(monkeypatch):
    assessment = funding.assess_funding(get_settings(), "FO-2026-117")
    assessment.retrievalContext = [funding.FundingRationale(
        heading="Live evidence", text="Context for model use, not the public summary.",
        evidenceRefs=[DOCUMENT_ID],
    )]
    (narrative, model, _), client = _model_response(monkeypatch, assessment)
    request = client.chat.completions.create.call_args.kwargs
    facts = json.loads(request["messages"][1]["content"])

    assert facts["match gap"] == 450_000
    assert facts["pursuit status"] == "Pursue - pending"
    assert facts["retrieval context"][0]["text"] == "Context for model use, not the public summary."
    assert "retrievalContext" not in assessment.model_dump()
    assert request["model"] == "award-iq-reasoning"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert narrative.evidenceRefs == [DOCUMENT_ID]
    assert model == "gpt-5.6-luna-2026-07-09"


def test_model_summary_has_a_bounded_shape_without_truncating_or_falling_back(monkeypatch):
    assessment = funding.assess_funding(get_settings(), "FO-2026-117")
    with pytest.raises(FundingDataUnavailable, match="No canned-answer fallback"):
        _model_response(
            monkeypatch, assessment,
            text=f"Pursue - pending; gap $450,000 [{DOCUMENT_ID}]. " + "extra detail " * 200,
        )


@pytest.mark.parametrize("text,refs", [
    (f"Pursue - pending; gap $450,000 but confirmed $9,999,999 [{DOCUMENT_ID}].", None),
    (f"Pursue - pending; gap $450,000.55 [{DOCUMENT_ID}].", None),
    (f"Pursue - pending; gap $450,000 [{DOCUMENT_ID}] [DOC-INVENTED].", ["DOC-INVENTED"]),
    (f"Approved; gap $450,000 [{DOCUMENT_ID}].", None),
])
def test_model_rejects_changed_financials_status_or_unknown_citations(monkeypatch, text, refs):
    assessment = funding.assess_funding(get_settings(), "FO-2026-117")
    with pytest.raises(FundingDataUnavailable, match="grounding checks"):
        _model_response(monkeypatch, assessment, text=text, refs=refs)


def test_live_work_narrative_requires_a_work_citation(monkeypatch):
    assessment = funding.assess_funding(get_settings(), "FO-2026-117")
    assessment.workMode = "work_iq"
    with pytest.raises(FundingDataUnavailable, match="grounding checks"):
        _model_response(monkeypatch, assessment)
    work_id = next(item.refId for item in assessment.evidence if item.source == Source.WORK)
    (result, _, _), client = _model_response(
        monkeypatch, assessment,
        text=f"Pursue - pending; gap $450,000 [{DOCUMENT_ID}]. Coordination [{work_id}].",
        refs=[DOCUMENT_ID, work_id],
    )
    assert work_id in result.evidenceRefs
    assert "Include at least one Work IQ document citation" in (
        client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    )


def test_live_pipeline_never_reads_foundry_fixtures_and_preserves_structured_math(monkeypatch):
    settings = get_settings().model_copy(update={
        "USE_LIVE_FABRIC": True, "USE_LIVE_FOUNDRY": True, "USE_LIVE_FUNDING_LLM": True,
    })
    rows = {name: funding._read_rows(settings.DATA_DIR, name) for name in FUNDING_TABLES}
    monkeypatch.setattr(funding, "read_funding_tables", lambda _: rows)
    original_citation = funding._citation

    def citation(data_dir, document):
        assert document["source"] != "foundry", "Live mode read a packaged Foundry document"
        return original_citation(data_dir, document)

    monkeypatch.setattr(funding, "_citation", citation)
    monkeypatch.setattr(funding, "retrieve_funding_knowledge", lambda *_, **__: foundry.FundingKnowledge(
        "Live retrieved grant interpretation.", [
            Evidence(
                refId=DOCUMENT_ID, source=Source.FOUNDRY, title="Live Amendment 2",
                snippet="25% match", sourceType="Live Foundry IQ", url=None,
            ),
        ], "Real retrieval question", 123,
    ))
    monkeypatch.setattr(funding, "synthesize_funding_answer", lambda _, assessment: (
        foundry.FundingNarrative(
            answer="Live model narrative.", bottomLine="Conditional pursuit.",
            evidenceRefs=[DOCUMENT_ID],
        ), "gpt-5.6-luna", 456,
    ))
    result = funding.assess_funding(settings, "FO-2026-117")

    assert result.answer == "Live model narrative."
    assert result.matchGap == 450_000
    assert result.matchConfirmed == 1_800_000
    assert result.pursuitStatus == "Pursue - pending"
    assert result.knowledgeMode == "foundry_iq"
    assert result.narrativeModel == "gpt-5.6-luna"
    assert "Live retrieved grant interpretation." not in [item.text for item in result.rationale]
    assert result.retrievalContext[0].text == "Live retrieved grant interpretation."
    source = next(item for item in result.sourceMap if item["source"] == "foundry")
    assert source["durationMs"] == 123
    assert source["citations"] == [DOCUMENT_ID]
    all_refs = {item.refId for item in result.evidence}
    assert all(
        set(item.evidenceRefs) <= all_refs
        for item in [*result.criteria, *result.rationale, *result.tasks, *result.criticalPath]
    )


def test_live_narrative_requires_real_knowledge_configuration():
    settings = get_settings().model_copy(update={"USE_LIVE_FUNDING_LLM": True})
    with pytest.raises(SettingsConfigurationError, match="USE_LIVE_FOUNDRY"):
        settings.validate_runtime_configuration()
