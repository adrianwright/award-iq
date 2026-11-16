# Award IQ backend

`services/api/app/funding.py` composes the active FO-2026-117 assessment from generated Fabric
funding tables and versioned Foundry/Work/external evidence. It selects the latest amendment
effective on or before the fixture as-of date, computes required match from the amendment rate and
eligible-cost basis, and counts only confirmed match sources.

The FastAPI application exposes:

- `POST /api/funding/ask` for a single grounded result.
- `POST /api/funding/ask/stream` for plan, source retrieval, and final result events.
- `GET /api/evidence/doc` for safe allowlisted synthetic citation documents.

The external provider in this mock slice is a local synthetic guidance file, not live web search.
M365-style records are local fixtures, not a live Work IQ session. Exceptions are returned as
errors; no mock result claims an integration was reached.

The historical `/api/ask` clinical orchestrator remains separate and is not called by the Award IQ
frontend. It is not part of the grant assessment boundary.
