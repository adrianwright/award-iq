# Award IQ backend

`services/api/app/funding.py` selects the opportunity named in a question from the generated linked
Fabric records and composes an evidence-backed assessment from versioned Foundry/Work/external
documents. It selects the latest effective amendment, reconciles project budget lines, de-duplicates
match by allocation ID, calculates confirmed/proposed amounts using integer USD, and derives
eligibility states and the dependency-ordered critical path from the source records.

The FastAPI application exposes:

- `POST /api/funding/ask` for a single grounded result.
- `POST /api/funding/ask/stream` for plan, source retrieval, and final result events.
- `GET /api/evidence/doc` for safe allowlisted synthetic citation documents.

The external provider in this mock slice is a local synthetic guidance file, not live web search.
M365-style records are local fixtures, not a live Work IQ session. Unknown data remains unknown;
counterfactual completion of a blocker does not change dated human approval records. Exceptions are
returned as errors; no mock result claims an integration was reached.

The historical `/api/ask` clinical orchestrator remains separate and is not called by the Award IQ
frontend. It is not part of the grant assessment boundary.
