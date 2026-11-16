from __future__ import annotations

import asyncio
import html as _html
import json
import re
import threading
from contextlib import suppress
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse

from app.auth import AuthenticatedUser, require_api_user
from app.config import get_settings
from app.fabric_status import get_fabric_status
from app.funding import FundingAssessment, FundingSourceProgress, assess_funding
from app.sources.fabric_funding import FundingDataUnavailable
from app.schemas import AskRequest
from app.workiq import WorkIQClient, WorkIQError

settings = get_settings()

_ALLOWED_DOC_DIRS = {"foundry_docs", "work", "web", "funding_ops"}
_DOC_NAME = re.compile(r"[A-Za-z0-9._-]+\.(md|json)$")

app = FastAPI(title="Award IQ API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "mode": settings.mode}


@app.get("/api/fabric/status")
def fabric_status() -> dict[str, str | None]:
    """Read-only running/paused state of the backing Fabric F64 capacity, so the UI can tell users
    whether a live assessment will work. Never errors: any failure degrades to state "Unknown"."""
    return get_fabric_status(settings).to_dict()


@app.get("/api/evidence/doc", response_class=HTMLResponse)
def evidence_doc(path: str) -> HTMLResponse:
    """Serve a cited synthetic source document (from data/foundry_docs or data/work) so citation
    links open the real source content in a browser. The indexed Foundry IQ blobs are private and
    firewalled, so raw blob URLs cannot open; these local docs are the same content that was indexed.
    Path is restricted to a whitelist of directories and validated against traversal."""
    parts = path.split("/")
    if len(parts) != 2 or parts[0] not in _ALLOWED_DOC_DIRS or not _DOC_NAME.fullmatch(parts[1]):
        raise HTTPException(status_code=404, detail="Document not found")
    subdir, name = parts
    base_dir = (
        settings.DATA_DIR / "fabric" / "funding_ops"
        if subdir == "funding_ops"
        else settings.DATA_DIR / subdir
    )
    base = base_dir.resolve()
    target = (base / name).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="Document not found")

    body = _html.escape(target.read_text(encoding="utf-8"))
    title = _html.escape(name)
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>"
        "body{font:14px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:820px;"
        "margin:2rem auto;padding:0 1.25rem;color:#16213e;background:#fafafa}"
        "pre{white-space:pre-wrap;word-wrap:break-word;background:#fff;border:1px solid #e6e6ef;"
        "border-radius:8px;padding:1.25rem}"
        ".src{color:#6b7280;font-size:12px;margin-bottom:1rem;text-transform:uppercase;"
        "letter-spacing:.05em}</style></head>"
        f"<body><div class='src'>Award IQ synthetic source document &middot; {title}</div>"
        f"<pre>{body}</pre></body></html>"
    )
    return HTMLResponse(page)


@app.post("/api/funding/ask", response_model=FundingAssessment)
def ask_funding(
    request: AskRequest,
    user: AuthenticatedUser | None = Depends(require_api_user),
) -> FundingAssessment:
    """Assess synthetic funding records from the configured authoritative data source."""
    try:
        return assess_funding(settings, request.question, user_access_token=user.access_token if user else None)
    except FundingDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/workiq/check")
def check_workiq(
    notice_id: Literal["FO-2026-117", "FO-2026-204", "FO-2026-330"] | None = None,
    user: AuthenticatedUser | None = Depends(require_api_user),
) -> dict[str, str | int]:
    """Check connectivity, or explicitly verify one notice without changing normal assessments."""
    if user is None:
        raise HTTPException(status_code=401, detail="A signed-in user is required for Work IQ.")
    if notice_id is not None:
        try:
            assessment = assess_funding(
                settings.model_copy(update={"USE_LIVE_WORK": True}),
                notice_id,
                user_access_token=user.access_token,
            )
        except FundingDataUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        citations = [item for item in assessment.evidence if item.source.value == "work"]
        if assessment.workMode != "work_iq" or not citations:
            raise HTTPException(status_code=503, detail="No verified live Work IQ evidence was returned.")
        return {
            "status": "verified",
            "noticeId": notice_id,
            "citationCount": len(citations),
            "message": f"{notice_id}: live Work IQ evidence and final assessment verified.",
        }
    try:
        answer = WorkIQClient(settings).ask(
            user_assertion=user.access_token,
            question=(
                "This is an Award IQ connection check. Reply with exactly AWARD_IQ_CONNECTED. "
                "Do not search, read, summarize or change any workplace data. Do not use any tools."
            ),
        )
    except WorkIQError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if answer.text.strip() != "AWARD_IQ_CONNECTED":
        raise HTTPException(
            status_code=503,
            detail="Work IQ responded, but did not return the expected connection-check acknowledgment.",
        )
    return {
        "status": "connected",
        "durationMs": answer.duration_ms,
        "message": "Work IQ responded through delegated authentication. Document access is not yet verified.",
    }


@app.post("/api/funding/ask/stream")
async def ask_funding_stream(
    request: AskRequest,
    user: AuthenticatedUser | None = Depends(require_api_user),
) -> EventSourceResponse:
    """Stream funding progress; live-source and model failures never fall back to fixtures."""
    async def events():
        sources = [
            ("foundry", "Funding notice and current amendment"),
            ("fabric", "Grant operations and match records"),
            ("work", "Proposal tasks and reviewer calendar"),
            ("web", "Synthetic agency guidance snapshot"),
        ]
        yield {
            "event": "plan",
            "data": json.dumps({"steps": ["Check current notice and amendment", "Reconcile confirmed match and eligibility evidence", "Review proposal tasks and deadlines", "Prepare human-review assessment"]}),
        }
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[FundingSourceProgress | None] = asyncio.Queue()
        closed = threading.Event()

        def progress(update: FundingSourceProgress) -> None:
            if not closed.is_set():
                loop.call_soon_threadsafe(queue.put_nowait, update)

        task = asyncio.create_task(run_in_threadpool(
            assess_funding, settings, request.question,
            user_access_token=user.access_token if user else None,
            on_progress=progress,
        ))
        task.add_done_callback(lambda _: queue.put_nowait(None))
        active_sources: set[str] = set()
        reported_failure = False
        try:
            while (update := await queue.get()) is not None:
                searching = update.status == "searching"
                if searching:
                    active_sources.add(update.source.value)
                else:
                    active_sources.discard(update.source.value)
                reported_failure = reported_failure or update.status == "failed"
                yield {
                    "event": "source_query" if searching else "source_result",
                    "data": json.dumps({**update.model_dump(mode="json"), "query": request.question}),
                }
            preliminary = await task
        except FundingDataUnavailable as exc:
            if not reported_failure:
                for source in sorted(active_sources):
                    yield {
                        "event": "source_result",
                        "data": json.dumps({
                            "source": source, "status": "failed", "summary": str(exc),
                            "citations": [], "durationMs": 0,
                        }),
                    }
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}
            return
        finally:
            closed.set()
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        retrieved = {item["source"]: item for item in preliminary.sourceMap}
        for source, label in sources:
            source_result = retrieved[source]
            state = source_result["status"]
            citations = source_result["citations"]
            summary = (
                source_result["summary"]
                if citations
                else "No synthetic evidence is available for this source and opportunity."
            )
            yield {
                "event": "source_result",
                "data": json.dumps({
                    "source": source,
                    "status": state,
                    "summary": summary,
                    "citations": citations,
                    "durationMs": source_result["durationMs"],
                }),
            }
        yield {"event": "final", "data": json.dumps({"result": preliminary.model_dump()})}

    return EventSourceResponse(events())
