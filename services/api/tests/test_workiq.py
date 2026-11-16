from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.workiq import (
    WorkIQAttribution,
    WorkIQClient,
    WorkIQProtocolError,
    WorkIQRequestError,
    WorkIQTokenExchangeError,
    _extract_attributions,
    _parse_retrieval,
    ask_with_access_token,
)


def _retrieval_payload(**updates):
    payload = {
        "results": [{
            "id": "h1", "markdown": "Current match task is open. [^h1]",
            "webUrl": "https://contoso.sharepoint.com/award/tracker.md",
            "entityType": "Files", "contentProtection": "allowed",
            "sensitivityLabel": {"displayName": "Confidential"},
        }],
        "resultCount": 1, "stoppedReason": "completed",
    }
    payload.update(updates)
    return {"application/vnd.ms-workiq.retrieval": payload}


def test_retrieval_parses_structured_results_and_preserves_source_security_metadata():
    documents = _parse_retrieval(_retrieval_payload(), is_error=False)
    assert documents[0].citation_id == "h1"
    assert documents[0].markdown.endswith("[^h1]")
    assert documents[0].url == "https://contoso.sharepoint.com/award/tracker.md"
    assert documents[0].sensitivity_label == {"displayName": "Confidential"}
    assert _parse_retrieval(_retrieval_payload(results=[], resultCount=0), is_error=False) == ()


@pytest.mark.parametrize("changes,is_error", [
    ({}, True),
    ({"stoppedReason": "error"}, False),
    ({"stoppedReason": "cancelled"}, False),
    ({"resultCount": 2}, False),
])
def test_retrieval_does_not_accept_failed_cancelled_or_partial_results(changes, is_error):
    with pytest.raises(WorkIQProtocolError):
        _parse_retrieval(_retrieval_payload(**changes), is_error=is_error)


@pytest.mark.parametrize("field,value", [
    ("contentProtection", None), ("contentProtection", "blocked"),
    ("webUrl", "javascript:alert(1)"), ("webUrl", None),
    ("entityType", "Email"), ("markdown", ""),
])
def test_retrieval_rejects_unprotected_or_unidentifiable_sources(field, value):
    structured = _retrieval_payload()
    structured["application/vnd.ms-workiq.retrieval"]["results"][0][field] = value
    with pytest.raises(WorkIQProtocolError):
        _parse_retrieval(structured, is_error=False)


def test_retrieval_uses_obo_and_discovers_tool_before_scoped_call(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    import mcp
    from mcp.client import streamable_http

    calls = []

    @asynccontextmanager
    async def transport(url, *, headers, **kwargs):
        assert url == "https://workiq.svc.cloud.microsoft/mcp"
        assert headers == {"Authorization": "Bearer work-iq-token"}
        yield None, None, None

    class Session:
        def __init__(self, *_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def initialize(self):
            calls.append("initialize")

        async def list_tools(self, **kwargs):
            calls.append("list")
            return SimpleNamespace(
                tools=[SimpleNamespace(name="retrieve", inputSchema={"type": "object"})],
                nextCursor=None,
            )

        async def call_tool(self, name, arguments, **kwargs):
            calls.append(name)
            assert arguments["strategy"] == "grounding"
            assert arguments["capabilities"] == [{
                "name": "OneDriveAndSharePoint",
                "items_by_url": [{"url": "https://contoso.sharepoint.com/award/tracker.md"}],
            }]
            return SimpleNamespace(structuredContent=_retrieval_payload(), isError=False)

    monkeypatch.setattr(mcp, "ClientSession", Session)
    monkeypatch.setattr(streamable_http, "streamablehttp_client", transport)
    answer = WorkIQClient(_settings(), obo_application=_OboSuccess()).retrieve(
        user_assertion="incoming-token", query="Find the match task",
        document_urls=["https://contoso.sharepoint.com/award/tracker.md"],
    )
    assert calls == ["initialize", "list", "retrieve"]
    assert len(answer.documents) == 1


class _OboSuccess:
    def acquire_token_on_behalf_of(self, *, user_assertion: str, scopes: list[str]) -> dict[str, str]:
        assert user_assertion == "incoming-token"
        assert scopes == ["api://workiq.svc.cloud.microsoft/.default"]
        return {"access_token": "work-iq-token"}


class _OboFailure:
    def acquire_token_on_behalf_of(self, *, user_assertion: str, scopes: list[str]) -> dict[str, str]:
        return {"error": "invalid_grant", "error_description": "consent is missing"}


def _settings() -> Settings:
    return Settings(_env_file=None, WORK_IQ_TIMEOUT_SECONDS=5)


def test_work_iq_success_parses_a2a_task_and_sends_required_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["A2A-Version"] == "1.0"
        assert request.headers["Authorization"].endswith("work-iq-token")
        assert payload["method"] == "SendMessage"
        assert payload["params"]["message"]["role"] == "ROLE_USER"
        return httpx.Response(
            200,
            request=request,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "task": {
                        "id": "task-1",
                        "contextId": "context-1",
                        "status": {
                            "state": "TASK_STATE_COMPLETED",
                            "message": {
                                "metadata": {
                                    "attributions": [
                                        {
                                            "attributionType": "Citation",
                                            "providerDisplayName": "Proposal review summary",
                                            "seeMoreWebUrl": "https://contoso.sharepoint.com/proposal-review",
                                        },
                                        {
                                            "attributionType": "Annotation",
                                            "providerDisplayName": "Dana",
                                            "seeMoreWebUrl": "https://contoso.example/people/dana",
                                        },
                                        {
                                            "attributionType": "Citation",
                                            "providerDisplayName": "Unsafe",
                                            "seeMoreWebUrl": "javascript:alert(1)",
                                        },
                                        {
                                            "attributionType": "Unsupported",
                                            "providerDisplayName": "Unknown source",
                                            "seeMoreWebUrl": "https://contoso.example/source",
                                        },
                                        "malformed attribution",
                                    ]
                                }
                            },
                        },
                        "artifacts": [
                            {
                                "artifactId": "answer-1",
                                "parts": [{"text": "Coordinator Dana owns the match confirmation task."}],
                            }
                        ],
                    }
                },
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    answer = WorkIQClient(
        _settings(),
        obo_application=_OboSuccess(),
        http_client=http_client,
    ).ask(user_assertion="incoming-token", question="Find the owner")

    assert answer.text == "Coordinator Dana owns the match confirmation task."
    assert answer.task_id == "task-1"
    assert answer.context_id == "context-1"
    assert answer.rejected_attribution_count == 3
    assert answer.attributions == (
        WorkIQAttribution(
            title="Proposal review summary",
            url="https://contoso.sharepoint.com/proposal-review",
        ),
        WorkIQAttribution(
            title="Dana",
            url="https://contoso.example/people/dana",
            attribution_type="annotation",
        ),
    )






def test_work_iq_finds_nested_and_url_less_citations() -> None:
    response = {
        "result": {
            "task": {
                "artifacts": [
                    {
                        "parts": [
                            {
                                "text": "Answer",
                                "metadata": {
                                    "attributions": [
                                        {
                                            "attributionType": "Citation",
                                            "providerDisplayName": "Coordinator task",
                                        },
                                        {
                                            "attributionType": "Citation",
                                            "providerDisplayName": "Proposal review summary",
                                            "seeMoreWebUrl": "https://contoso.sharepoint.com/summary",
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        }
    }

    attributions, diagnostics = _extract_attributions(response)

    assert attributions == (
        WorkIQAttribution(title="Coordinator task", url=None),
        WorkIQAttribution(
            title="Proposal review summary",
            url="https://contoso.sharepoint.com/summary",
        ),
    )
    assert diagnostics.candidate_count == 2
    assert diagnostics.accepted_count == 2


def test_work_iq_parses_reference_data_parts_and_logs_only_shape(caplog) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            request=request,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "task": {
                        "id": "task-reference",
                        "contextId": "context-reference",
                        "status": {"state": "TASK_STATE_COMPLETED"},
                        "artifacts": [
                            {
                                "artifactId": "answer",
                                "parts": [
                                    {"text": "The coordinator owns the next step."},
                                    {
                                        "mediaType": "application/vnd.workiq-reference",
                                        "data": {
                                            "references": [
                                                {
                                                    "title": "Coordinator handoff",
                                                    "webUrl": "https://contoso.sharepoint.com/private/handoff",
                                                }
                                            ]
                                        },
                                    },
                                ],
                            }
                        ],
                    }
                },
            },
        )

    with caplog.at_level("INFO", logger="app.workiq"):
        answer = ask_with_access_token(
            access_token="work-iq-token",
            question="Find the owner",
            endpoint="https://workiq.example/a2a/",
            timeout_seconds=5,
            timezone_offset_minutes=-300,
            timezone="America/Chicago",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    assert answer.attributions == (
        WorkIQAttribution(
            title="Coordinator handoff",
            url="https://contoso.sharepoint.com/private/handoff",
            attribution_type="reference",
        ),
    )
    assert "candidates=1 accepted=1 types=reference=1 reference_parts=1 invalid_urls=0" in caplog.text
    assert "contoso.sharepoint.com" not in caplog.text




def test_work_iq_surfaces_obo_failure() -> None:
    with pytest.raises(WorkIQTokenExchangeError, match="invalid_grant"):
        WorkIQClient(_settings(), obo_application=_OboFailure()).ask(
            user_assertion="incoming-token",
            question="Find the owner",
        )


def test_work_iq_surfaces_http_failure() -> None:
    http_client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(503, request=request))
    )
    with pytest.raises(WorkIQRequestError, match="HTTP 503"):
        WorkIQClient(
            _settings(),
            obo_application=_OboSuccess(),
            http_client=http_client,
        ).ask(user_assertion="incoming-token", question="Find the owner")


def test_work_iq_surfaces_quota_error_detail_and_request_id() -> None:
    http_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                403,
                request=request,
                headers={"request-id": "request-123"},
                json={
                    "error": "QuotaExhausted",
                    "message": "No AI credits are currently available for this user.",
                },
            )
        )
    )
    with pytest.raises(
        WorkIQRequestError,
        match=r"QuotaExhausted.*No AI credits.*request-123",
    ):
        WorkIQClient(
            _settings(),
            obo_application=_OboSuccess(),
            http_client=http_client,
        ).ask(user_assertion="incoming-token", question="Find the owner")


def test_work_iq_surfaces_nested_error_detail() -> None:
    http_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                403,
                request=request,
                json={
                    "error": {
                        "code": "QuotaExhausted",
                        "message": "The assigned spending policy has reached its limit.",
                    }
                },
            )
        )
    )
    with pytest.raises(
        WorkIQRequestError,
        match=r"QuotaExhausted.*assigned spending policy",
    ):
        WorkIQClient(
            _settings(),
            obo_application=_OboSuccess(),
            http_client=http_client,
        ).ask(user_assertion="incoming-token", question="Find the owner")


def test_work_iq_rejects_json_rpc_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            request=request,
            json={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": "agent unavailable"},
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(WorkIQProtocolError, match="agent unavailable"):
        WorkIQClient(
            _settings(),
            obo_application=_OboSuccess(),
            http_client=http_client,
        ).ask(user_assertion="incoming-token", question="Find the owner")
