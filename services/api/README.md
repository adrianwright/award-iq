# Award IQ API

FastAPI serves deterministic, synthetic funding-readiness assessments for three linked opportunities at
`POST /api/funding/ask` and its streamed equivalent at `POST /api/funding/ask/stream`.

Run locally without Azure:

```bash
python -m pip install -r services/api/requirements.lock.txt
APP_ENVIRONMENT=development USE_LIVE_FOUNDRY=false USE_LIVE_FABRIC=false \
USE_LIVE_WORK=false USE_LIVE_FUNDING_LLM=false \
python -m uvicorn app.main:app --app-dir services/api --port 8000
```

In local mode the funding routes resolve the requested notice from checked-in tables under
`data/fabric/funding_ops/` and synthetic evidence documents under `data/`. They default to
FO-2026-117 when a question does not identify a comparator. The routes do not write to Microsoft 365
or submit any grant materials.
`/api/evidence/doc` serves only allowlisted synthetic evidence; see
[`../../docs/api-contract.md`](../../docs/api-contract.md).

Connected mode reads Fabric SQL and optionally Foundry/Work IQ; live failures do not fall back
to fixtures. See `../../docs/deployment.md` for manual prerequisites.

Run the backend tests from the repository root with `python -m pytest services/api/tests`.
