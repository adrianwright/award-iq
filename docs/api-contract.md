# Award IQ funding API contract

## Assessment

`POST /api/funding/ask` accepts `{"question":"..."}` and resolves a linked synthetic opportunity
from the question, defaulting to FO-2026-117. Example comparator questions target FO-2026-204 and
FO-2026-330. `/api/funding/ask/stream` accepts the same payload and emits Server-Sent Events in the
order `plan`, `source_query`, `source_result`, and `final` (or `error`).

The final result includes the fixed scenario/as-of date, notice and deadline/timezone, project-cost
and requested-grant basis, current pursuit status, synthesized evidence-backed rationale,
eligibility criteria, amendment impact, match arithmetic, partner evidence, task owners/dependencies,
ordered critical path, review timing, legal availability, unknown submission requirements, citations,
source map, and assessment trace.

All task actions are returned as `Drafted (not submitted)`. The current recorded `Pursue - pending`
status is not approval. The API does not write to Microsoft 365, Planner, agency systems, or the
structured fixture data.

## Evidence and health

- `GET /api/evidence/doc?path=...` serves Markdown or JSON from allowlisted `foundry_docs`, `work`,
  `web`, or synthetic `funding_ops` evidence. Traversal and unsupported filenames return 404.
- `GET /healthz` reports API health and configured mode.
- `GET /api/fabric/status` reports the optional live Fabric capacity state; local funding assessment
  does not depend on Azure or this route.

Funding evidence/document IDs (for example `FO-2026-117`, `TASK-117-PARTNER`, and
`DOC-FO117-AMD2`) are preserved in citations and workflow records. Source version/date provenance is
in the cited fixture's front matter and response metadata. External evidence is a local synthetic
snapshot, never a claim of a live agency connection.

`POST /api/workiq/check` requires a signed-in user and checks delegated Work IQ connectivity.
An optional allowlisted `notice_id` runs a live Work IQ assessment for that notice only.
The old `/api/ask` and cohort routes are removed and return 404.
