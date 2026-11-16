from __future__ import annotations

import asyncio
import time
import uuid
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
import msal

from app.config import Settings
from app.keyvault_certificate import (
    CertificateCredentialError,
    CertificateCredentialProvider,
    create_certificate_credential_provider,
)

logger = logging.getLogger(__name__)
WORK_IQ_REFERENCE_MEDIA_TYPE = "application/vnd.workiq-reference"


class WorkIQError(RuntimeError):
    """Base class for typed Work IQ integration failures."""


class WorkIQConfigurationError(WorkIQError):
    pass


class WorkIQTokenExchangeError(WorkIQError):
    pass


class WorkIQRequestError(WorkIQError):
    pass


class WorkIQProtocolError(WorkIQError):
    pass


class OboApplication(Protocol):
    def acquire_token_on_behalf_of(self, *, user_assertion: str, scopes: list[str]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class WorkIQAttribution:
    title: str
    url: str | None
    attribution_type: str = "citation"


@dataclass(frozen=True)
class _AttributionCandidate:
    value: dict[str, Any]
    default_type: str = ""


@dataclass(frozen=True)
class _AttributionDiagnostics:
    candidate_count: int
    accepted_count: int
    reference_part_count: int
    invalid_url_count: int
    malformed_count: int
    type_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class WorkIQAnswer:
    text: str
    task_id: str | None
    context_id: str | None
    duration_ms: int
    attributions: tuple[WorkIQAttribution, ...] = ()
    rejected_attribution_count: int = 0


@dataclass(frozen=True)
class WorkIQDocument:
    citation_id: str
    markdown: str
    url: str
    sensitivity_label: dict[str, Any]
    drive_id: str | None = None
    item_id: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class WorkIQRetrieval:
    documents: tuple[WorkIQDocument, ...]
    duration_ms: int


def _parse_retrieval(structured: dict[str, Any] | None, *, is_error: bool) -> tuple[WorkIQDocument, ...]:
    payload = (structured or {}).get("application/vnd.ms-workiq.retrieval")
    if not isinstance(payload, dict):
        raise WorkIQProtocolError("Work IQ returned no structured retrieval payload.")
    if is_error or payload.get("stoppedReason") != "completed":
        code = payload.get("errorCode", payload.get("stoppedReason", "unknown"))
        raise WorkIQProtocolError(f"Work IQ retrieval did not complete ({code}); no fallback was used.")
    results = payload.get("results")
    if not isinstance(results, list) or payload.get("resultCount") != len(results):
        raise WorkIQProtocolError("Work IQ returned an invalid or partial retrieval result.")
    documents: list[WorkIQDocument] = []
    seen: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            raise WorkIQProtocolError("Work IQ returned malformed source metadata.")
        if result.get("contentProtection") != "allowed":
            raise WorkIQProtocolError("Work IQ did not explicitly allow use of retrieved source content.")
        citation_id = result.get("id")
        markdown = result.get("markdown")
        url = _validated_web_url(result.get("webUrl"))
        label = result.get("sensitivityLabel", {})
        if (
            not isinstance(citation_id, str) or not citation_id or citation_id in seen
            or not isinstance(markdown, str) or not markdown.strip() or url is None
            or not isinstance(label, dict) or result.get("entityType") != "Files"
        ):
            raise WorkIQProtocolError("Work IQ returned an invalid or unidentifiable document.")
        seen.add(citation_id)
        drive_id = result.get("driveId")
        item_id = result.get("itemId")
        if any(value is not None and (not isinstance(value, str) or not value) for value in (drive_id, item_id)):
            raise WorkIQProtocolError("Work IQ returned malformed drive/item identity metadata.")
        metadata = result.get("resourceMetadata")
        document_metadata = metadata.get("document") if isinstance(metadata, dict) else None
        title = document_metadata.get("title") if isinstance(document_metadata, dict) else None
        documents.append(WorkIQDocument(
            citation_id, markdown, url, label, drive_id, item_id,
            title if isinstance(title, str) else None,
        ))
    return tuple(documents)


async def _retrieve_with_access_token(
    settings: Settings, access_token: str, query: str, document_urls: list[str],
) -> tuple[WorkIQDocument, ...]:
    from jsonschema import validate
    from jsonschema.exceptions import SchemaError, ValidationError
    from mcp import ClientSession, McpError
    from mcp.client.streamable_http import streamablehttp_client

    arguments = {
        "query": query,
        "strategy": "grounding",
        "capabilities": [{
            "name": "OneDriveAndSharePoint",
            "items_by_url": [{"url": url} for url in document_urls],
        }],
        "includeDeveloperCard": False,
    }
    try:
        async with asyncio.timeout(settings.WORK_IQ_TIMEOUT_SECONDS):
            async with streamablehttp_client(
                settings.WORK_IQ_MCP_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=settings.WORK_IQ_TIMEOUT_SECONDS,
                sse_read_timeout=settings.WORK_IQ_TIMEOUT_SECONDS,
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    cursor = None
                    for _ in range(10):
                        listing = await session.list_tools(cursor=cursor)
                        tool = next((tool for tool in listing.tools if tool.name == "retrieve"), None)
                        if tool is not None:
                            break
                        cursor = listing.nextCursor
                        if not cursor:
                            raise WorkIQConfigurationError("Work IQ retrieve is unavailable for this tenant.")
                    else:
                        raise WorkIQConfigurationError("Work IQ tool discovery exceeded the supported page limit.")
                    validate(arguments, tool.inputSchema)
                    result = await session.call_tool(
                        tool.name, arguments,
                        read_timeout_seconds=timedelta(seconds=settings.WORK_IQ_TIMEOUT_SECONDS),
                    )
                    return _parse_retrieval(result.structuredContent, is_error=result.isError)
    except (httpx.HTTPError, McpError, TimeoutError, SchemaError, ValidationError) as exc:
        logger.warning("Work IQ structured retrieval failed: type=%s", type(exc).__name__)
        raise WorkIQRequestError(
            "Work IQ structured retrieval failed. Check MCP availability, consent and source access; "
            "no alternate retrieval or fallback was attempted."
        ) from exc
    except ExceptionGroup as exc:
        # MCP transports can wrap a typed service or protocol failure in a task-group exception.
        failures = list(exc.exceptions)
        while failures:
            failure = failures.pop(0)
            if isinstance(failure, WorkIQError):
                raise failure from exc
            if isinstance(failure, ExceptionGroup):
                failures.extend(failure.exceptions)
        logger.warning("Work IQ MCP transport failed: type=%s", type(exc).__name__)
        raise WorkIQRequestError("Work IQ MCP transport failed; no fallback was attempted.") from exc


def _create_obo_application(
    settings: Settings,
    certificate_provider: CertificateCredentialProvider,
) -> OboApplication:
    missing = [
        name
        for name, value in (
            ("AZURE_TENANT_ID", settings.AZURE_TENANT_ID),
            ("WORK_IQ_CLIENT_ID", settings.WORK_IQ_CLIENT_ID),
        )
        if not value.strip()
    ]
    if missing:
        raise WorkIQConfigurationError(f"Work IQ OBO configuration is missing: {', '.join(missing)}")
    try:
        certificate = certificate_provider.get_client_credential()
    except CertificateCredentialError as exc:
        raise WorkIQConfigurationError(str(exc)) from exc
    return msal.ConfidentialClientApplication(
        client_id=settings.WORK_IQ_CLIENT_ID,
        authority=settings.obo_authority,
        client_credential=certificate,
        timeout=settings.WORK_IQ_TIMEOUT_SECONDS,
    )


def _extract_text(response: dict[str, Any]) -> tuple[str, str | None, str | None]:
    if error := response.get("error"):
        if isinstance(error, dict):
            code = error.get("code", "unknown")
            message = error.get("message", "Work IQ returned a JSON-RPC error")
            raise WorkIQProtocolError(f"Work IQ JSON-RPC error {code}: {message}")
        raise WorkIQProtocolError(f"Work IQ JSON-RPC error: {error}")

    result = response.get("result")
    if not isinstance(result, dict):
        raise WorkIQProtocolError("Work IQ response is missing result")

    task = result.get("task")
    if isinstance(task, dict):
        status = task.get("status")
        state = str(status.get("state", "")) if isinstance(status, dict) else ""
        if state in {"TASK_STATE_FAILED", "TASK_STATE_REJECTED", "TASK_STATE_CANCELED"}:
            raise WorkIQProtocolError(f"Work IQ task ended in {state}")
        artifacts = task.get("artifacts")
        if not isinstance(artifacts, list):
            artifacts = []
        texts = _texts_from_parts(
            part
            for artifact in artifacts
            if isinstance(artifact, dict)
            for part in _part_list(artifact)
        )
        if texts:
            return "\n".join(texts), _string_or_none(task.get("id")), _string_or_none(task.get("contextId"))

    message = result.get("message")
    if isinstance(message, dict):
        texts = _texts_from_parts(message.get("parts", []))
        if texts:
            return "\n".join(texts), None, _string_or_none(message.get("contextId"))

    raise WorkIQProtocolError("Work IQ response contains no text answer")


def _texts_from_parts(parts: Any) -> list[str]:
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
            texts.append(part["text"].strip())
    return texts


def _part_list(container: dict[str, Any]) -> list[Any]:
    parts = container.get("parts")
    return parts if isinstance(parts, list) else []


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _reference_items(value: Any) -> tuple[list[dict[str, Any]], int]:
    if isinstance(value, list):
        items = [item for item in value if isinstance(item, dict)]
        return items, len(value) - len(items) + (1 if not value else 0)
    if not isinstance(value, dict):
        return [], 1
    items: list[dict[str, Any]] = []
    malformed_count = 0
    has_nested = False
    for key in ("attributions", "citations", "references"):
        nested = value.get(key)
        if isinstance(nested, list):
            has_nested = True
            items.extend(item for item in nested if isinstance(item, dict))
            malformed_count += sum(not isinstance(item, dict) for item in nested)
            malformed_count += 1 if not nested else 0
    if has_nested:
        return items, malformed_count
    return [value], 0


def _attribution_candidates(
    response: dict[str, Any],
) -> tuple[list[_AttributionCandidate], int, int]:
    result = response.get("result")
    if not isinstance(result, dict):
        return [], 0, 0

    candidates: list[_AttributionCandidate] = []
    seen_candidates: set[int] = set()
    reference_part_count = 0
    malformed_count = 0
    for container in _walk_dicts(result):
        for part in _part_list(container):
            if not isinstance(part, dict):
                continue
            media_type = _string_or_none(part.get("mediaType")) or _string_or_none(
                part.get("mimeType")
            )
            if media_type != WORK_IQ_REFERENCE_MEDIA_TYPE:
                continue
            reference_part_count += 1
            reference_items, malformed = _reference_items(part.get("data"))
            malformed_count += malformed
            for item in reference_items:
                if id(item) not in seen_candidates:
                    candidates.append(
                        _AttributionCandidate(value=item, default_type="reference")
                    )
                    seen_candidates.add(id(item))
        for key, default_type in (
            ("attributions", "citation"),
            ("citations", "citation"),
            ("references", "reference"),
        ):
            raw_items = container.get(key)
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, dict):
                    malformed_count += 1
                elif id(item) not in seen_candidates:
                    candidates.append(
                        _AttributionCandidate(value=item, default_type=default_type)
                    )
                    seen_candidates.add(id(item))
    return candidates, reference_part_count, malformed_count


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    if isinstance(value, dict):
        containers.append(value)
        for nested in value.values():
            containers.extend(_walk_dicts(nested))
    elif isinstance(value, list):
        for nested in value:
            containers.extend(_walk_dicts(nested))
    return containers


def _extract_attributions(
    response: dict[str, Any],
) -> tuple[tuple[WorkIQAttribution, ...], _AttributionDiagnostics]:
    candidates, reference_part_count, malformed_count = _attribution_candidates(response)
    attributions: list[WorkIQAttribution] = []
    seen: set[tuple[str, str | None]] = set()
    invalid_url_count = 0
    type_counts: Counter[str] = Counter()
    for candidate in candidates:
        raw = candidate.value
        attribution_type = (
            _string_or_none(raw.get("attributionType")) or candidate.default_type or "unknown"
        ).lower()
        type_counts[
            attribution_type
            if attribution_type in {"citation", "annotation", "reference"}
            else "unsupported"
        ] += 1
        if attribution_type not in {"citation", "annotation", "reference"}:
            continue
        title = (
            _string_or_none(raw.get("providerDisplayName"))
            or _string_or_none(raw.get("title"))
            or _string_or_none(raw.get("name"))
            or "Work IQ source"
        )
        raw_url = next(
            (
                value
                for value in (
                    raw.get("seeMoreWebUrl"),
                    raw.get("webUrl"),
                    raw.get("url"),
                    raw.get("blobUrl"),
                )
                if value is not None
            ),
            None,
        )
        url = _validated_web_url(raw_url)
        if raw_url not in (None, "") and url is None:
            invalid_url_count += 1
            continue
        key = (title, url)
        if key in seen:
            continue
        attributions.append(
            WorkIQAttribution(
                title=title,
                url=url,
                attribution_type=attribution_type,
            )
        )
        seen.add(key)
    diagnostics = _AttributionDiagnostics(
        candidate_count=len(candidates),
        accepted_count=len(attributions),
        reference_part_count=reference_part_count,
        invalid_url_count=invalid_url_count,
        malformed_count=malformed_count,
        type_counts=tuple(sorted(type_counts.items())),
    )
    return tuple(attributions), diagnostics


def _validated_web_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def _http_error_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    message = payload.get("message")
    if isinstance(error, dict):
        code = _string_or_none(error.get("code"))
        nested_message = _string_or_none(error.get("message"))
        parts = [part for part in (code, nested_message) if part]
        return ": ".join(parts) if parts else None
    parts = [
        part
        for part in (
            _string_or_none(error),
            _string_or_none(message),
        )
        if part
    ]
    return ": ".join(parts) if parts else None


class WorkIQClient:
    def __init__(
        self,
        settings: Settings,
        *,
        obo_application: OboApplication | None = None,
        http_client: httpx.Client | None = None,
        certificate_provider: CertificateCredentialProvider | None = None,
    ) -> None:
        self.settings = settings
        self._obo_application = obo_application
        self._http_client = http_client
        self._certificate_provider = certificate_provider or create_certificate_credential_provider(
            settings
        )

    def _access_token(self, user_assertion: str) -> str:
        if not user_assertion:
            raise WorkIQTokenExchangeError("A delegated user token is required for Work IQ")

        application = self._obo_application or _create_obo_application(
            self.settings,
            self._certificate_provider,
        )
        token_result = application.acquire_token_on_behalf_of(
            user_assertion=user_assertion,
            scopes=[self.settings.WORK_IQ_SCOPE],
        )
        access_token = token_result.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            error = str(token_result.get("error", "token_exchange_failed"))
            description = str(token_result.get("error_description", "OBO token exchange returned no access token"))
            logger.warning("Work IQ OBO failed: error=%s description=%s", error, description)
            raise WorkIQTokenExchangeError(f"Work IQ OBO failed ({error})")
        return access_token

    def retrieve(
        self, *, user_assertion: str, query: str, document_urls: list[str],
    ) -> WorkIQRetrieval:
        access_token = self._access_token(user_assertion)
        started = time.perf_counter()
        documents = asyncio.run(
            _retrieve_with_access_token(self.settings, access_token, query, document_urls)
        )
        duration_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "Work IQ structured retrieval completed: documents=%d duration_ms=%d",
            len(documents), duration_ms,
        )
        return WorkIQRetrieval(documents, duration_ms)

    def ask(self, *, user_assertion: str, question: str) -> WorkIQAnswer:
        access_token = self._access_token(user_assertion)

        return ask_with_access_token(
            access_token=access_token,
            question=question,
            endpoint=self.settings.WORK_IQ_ENDPOINT,
            timeout_seconds=self.settings.WORK_IQ_TIMEOUT_SECONDS,
            timezone_offset_minutes=self.settings.WORK_IQ_TIMEZONE_OFFSET_MINUTES,
            timezone=self.settings.WORK_IQ_TIMEZONE,
            http_client=self._http_client,
        )


def ask_with_access_token(
    *,
    access_token: str,
    question: str,
    endpoint: str,
    timeout_seconds: float,
    timezone_offset_minutes: int,
    timezone: str,
    http_client: httpx.Client | None = None,
) -> WorkIQAnswer:
    """Send an A2A v1.0 message using an already-acquired delegated Work IQ token."""
    if not access_token:
        raise WorkIQTokenExchangeError("A delegated Work IQ access token is required")

    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "ROLE_USER",
                "messageId": str(uuid.uuid4()),
                "parts": [{"text": question}],
                "metadata": {
                    "Location": {
                        "timeZoneOffset": timezone_offset_minutes,
                        "timeZone": timezone,
                    }
                },
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "A2A-Version": "1.0",
    }

    started = time.perf_counter()
    owned_client = http_client is None
    client = http_client or httpx.Client(
        timeout=httpx.Timeout(timeout_seconds, connect=10.0)
    )
    try:
        response = client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise WorkIQRequestError("Work IQ request timed out") from exc
    except httpx.HTTPStatusError as exc:
        request_id_header = exc.response.headers.get("request-id") or exc.response.headers.get(
            "x-ms-request-id"
        )
        suffix = f" (request-id: {request_id_header})" if request_id_header else ""
        detail = _http_error_detail(exc.response)
        detail_suffix = f": {detail}" if detail else ""
        logger.warning(
            "Work IQ HTTP failure: status=%s request_id=%s detail=%s",
            exc.response.status_code,
            request_id_header or "unavailable",
            detail or "unavailable",
        )
        raise WorkIQRequestError(
            f"Work IQ returned HTTP {exc.response.status_code}{detail_suffix}{suffix}"
        ) from exc
    except httpx.HTTPError as exc:
        raise WorkIQRequestError("Work IQ request failed") from exc
    finally:
        if owned_client:
            client.close()

    try:
        body = response.json()
    except ValueError as exc:
        raise WorkIQProtocolError("Work IQ returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise WorkIQProtocolError("Work IQ returned an invalid JSON-RPC envelope")
    if body.get("error") is not None:
        _extract_text(body)
    if str(body.get("id")) != request_id:
        raise WorkIQProtocolError("Work IQ response id does not match the request")

    text, task_id, context_id = _extract_text(body)
    attributions, attribution_diagnostics = _extract_attributions(body)
    duration_ms = round((time.perf_counter() - started) * 1000)
    type_summary = ",".join(
        f"{name}={count}" for name, count in attribution_diagnostics.type_counts
    ) or "none"
    logger.info(
        "Work IQ attribution diagnostics: candidates=%d accepted=%d types=%s "
        "reference_parts=%d invalid_urls=%d malformed=%d",
        attribution_diagnostics.candidate_count,
        attribution_diagnostics.accepted_count,
        type_summary,
        attribution_diagnostics.reference_part_count,
        attribution_diagnostics.invalid_url_count,
        attribution_diagnostics.malformed_count,
    )
    logger.info(
        "Work IQ completed: task_id=%s attributions=%d duration_ms=%d",
        task_id or "unavailable",
        len(attributions),
        duration_ms,
    )
    return WorkIQAnswer(
        text=text,
        task_id=task_id,
        context_id=context_id,
        duration_ms=duration_ms,
        attributions=attributions,
        rejected_attribution_count=(
            attribution_diagnostics.invalid_url_count
            + attribution_diagnostics.malformed_count
            + dict(attribution_diagnostics.type_counts).get("unsupported", 0)
        ),
    )
