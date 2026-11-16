# Award IQ API

FastAPI serves the deterministic, synthetic FO-2026-117 funding-readiness assessment at
`POST /api/funding/ask` and its streamed equivalent at `POST /api/funding/ask/stream`.

Run locally without Azure:

```bash
python -m pip install -r services/api/requirements.lock.txt
APP_ENVIRONMENT=development USE_LIVE_FOUNDRY=false USE_LIVE_FABRIC=false \
USE_LIVE_WORK=false USE_LIVE_WEB=false USE_LIVE_AGENT=false \
python -m uvicorn app.main:app --app-dir services/api --port 8000
```

The funding route reads checked-in tables under `data/fabric/funding_ops/` and synthetic evidence
documents under `data/`. The routes do not write to Microsoft 365 or submit any grant materials.
`/api/evidence/doc` serves only allowlisted synthetic evidence; see
[`../../docs/api-contract.md`](../../docs/api-contract.md).

Run the backend tests from the repository root with `python -m pytest services/api/tests`.
