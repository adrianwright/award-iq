# Award IQ

Award IQ is a synthetic, human-reviewed grant eligibility and funding-readiness proof of concept.
It brings together **Foundry IQ** institutional funding knowledge, **Fabric IQ** structured grant
operations, and **Work IQ** proposal-team context. External agency guidance is shown as a synthetic
snapshot; it is not a live connection.

> **Synthetic decision support only.** The scenario is fictional, is not a funding decision, and is
> not validated for production use. Recommendations and next actions require human review. The
> application never approves funding, creates tasks, sends notifications, books meetings, or submits
> an application.

## Hero scenario

As of **2026-11-16**, notice **FO-2026-117, Community Resilience Infrastructure Grant**, closes
**2026-12-16, America/New_York** (30 calendar days). The $9,000,000 eligible-cost basis and
$6,750,000 grant request are explicit synthetic fixture-design assumptions. Current Amendment 2
requires a 25% local match ($2,250,000); $1,800,000 is confirmed, leaving a $450,000 gap. The
separate $450,000 reserve is proposed and is not counted. The recorded human disposition is
**Pursue - pending**, conditional on resolving the gap and obtaining a current regional-partner
commitment letter.

The answer also grounds conditional pursuit in the proposed project's measurable resilience target,
community needs snapshot, documented prior delivery, and the 2024 partner lead (whose award outcome
is unknown). These are reasons to consider pursuing, not evidence of award likelihood. The Nov 19
review slot is available but not booked or final approval; the partner letter follows it and is due
Nov 20. Legal/procurement review must also finish by Nov 20, before the reviewer's Nov 23–27 leave.

Two concise comparators exercise distinct outcomes: FO-2026-204 is ready for human submission review
but not submitted; FO-2026-330 fails the evidenced rural-geography condition. Use the example
questions in the UI or ask about either notice ID.

Jordan Lee (PM-01) owns the proposal and partner-letter task due 2026-11-20. Maria Santos (FIN-02)
owns match confirmation due 2026-11-18. The assessment also shows the 2026-11-19 executive-review
slot with Dr. Elena Ruiz and the legal/procurement deadline before Sam Patel's 2026-11-23–27
unavailability. These are evidence-backed constraints; the app does not claim that a meeting is
booked.

## Run locally

The deterministic local path uses only checked-in synthetic fixtures; it requires no Azure
credentials and no network-dependent evidence provider.

```powershell
./scripts/dev.ps1
```

The launcher starts the API at `http://localhost:8000` and the Vite UI at `http://localhost:5173`.
For manual startup, use Python 3.12 and Node 22:

```bash
# Terminal 1: API
python -m venv .venv
. .venv/bin/activate
python -m pip install -r services/api/requirements.lock.txt -r tools/requirements.lock.txt
export APP_ENVIRONMENT=development
export USE_LIVE_FOUNDRY=false USE_LIVE_FABRIC=false USE_LIVE_WORK=false
export USE_LIVE_WEB=false USE_LIVE_AGENT=false USE_LIVE_SPECIALISTS=false
cd services/api
uvicorn app.main:app --port 8000

# Terminal 2: frontend
cd apps/web
npm ci
npm run dev
```

The application starts on the pinned 2026-11-16 scenario and accepts editable, free-form funding
questions. Evidence links resolve to the synthetic versioned source files.

## Data and validation

The funding operations tables are defined in `data/fabric/funding_ops/generate.py`; the generator is
deterministic and the dictionary documents field types, nullable semantics, keys, joins, and source
precedence. Foundry-style notice/policy documents are in `data/foundry_docs/`, versioned proposal
workflow fixtures are in `data/work/`, and the scenario's semantic contract is
`data/ontology/funding_ontology.yaml`.

```bash
python data/fabric/funding_ops/generate.py
python tools/validate_consistency.py
python -m pytest services/api/tests
cd apps/web && npm test && npm run lint && npm run build
```

## Architecture and boundaries

```text
React/Vite -> FastAPI REST + SSE -> grant assessment
                                  +-> Foundry IQ synthetic corpus
                                  +-> Fabric IQ funding tables
                                  +-> Work IQ proposal workflow
                                  `-> external synthetic guidance
```

`POST /api/funding/ask` and `/api/funding/ask/stream` return a citation-backed assessment from the
offline fixture package. `/api/evidence/doc` serves only allowlisted source files. The existing
clinical proof-of-concept code is retained only for source-history/test compatibility and is not
used by the Award IQ user interface or funding assessment route. Optional Microsoft integration
paths remain explicit opt-ins; no cloud resource is provisioned or tenant seeded by the local
launcher.

## Provenance

The grant scenario and fixtures are synthetic and original to this repository. Historical product
attribution and MIT licensing are retained in [`LICENSE`](LICENSE). Foundry IQ, Fabric IQ, and Work
IQ are Microsoft integration-layer names, not product names.
