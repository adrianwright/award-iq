# Award IQ funding API contract

## Assessment

`POST /api/funding/ask` accepts `{"question":"..."}` and returns a synthetic assessment for
FO-2026-117. `/api/funding/ask/stream` accepts the same payload and emits Server-Sent Events in the
order `plan`, `source_query`, `source_result`, and `final` (or `error`).

The final result includes the fixed scenario/as-of date, notice and deadline, current pursuit status,
recommendation boundary, eligibility criteria, match basis and arithmetic, partner evidence, task
owners and due dates, review timing, legal availability, submission state, citations, source map, and
assessment trace.

All task actions are returned as `Drafted (not submitted)`. The current recorded `Pursue - pending`
status is not approval. The API does not write to Microsoft 365, Planner, agency systems, or the
structured fixture data.

## Evidence and health

- `GET /api/evidence/doc?path=...` serves Markdown or JSON from the allowlisted `foundry_docs`,
  `work`, or `web` fixture directories. Traversal and unsupported filenames return 404.
- `GET /healthz` reports API health and configured mode.
- `GET /api/fabric/status` reports the optional live Fabric capacity state; local funding assessment
  does not depend on Azure or this route.

Funding evidence IDs (for example `FO-2026-117` and `TASK-117-PARTNER`) are preserved in citations
and workflow records. Source version/date provenance is in the cited fixture's front matter and
content. External evidence is a local synthetic snapshot, never a claim of a live agency connection.

The earlier `/api/ask` and cohort routes remain for source-history compatibility and are not used by
the Award IQ application.
