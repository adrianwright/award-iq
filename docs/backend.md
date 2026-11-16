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

External guidance is always a packaged synthetic snapshot. Fabric SQL, Foundry retrieval/model
synthesis and delegated Work IQ are independently configured live sources; see configuration.md. Unknown data remains unknown;
counterfactual completion of a blocker does not change dated human approval records. Exceptions are
returned as errors; no mock result claims an integration was reached.

Authentication, certificate OBO, read-only Fabric capacity status and Work IQ diagnostics are
shared services. There is no separate legacy orchestrator or cohort route.
