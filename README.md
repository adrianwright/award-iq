# Award IQ

Evidence-backed **grant eligibility and funding-readiness decision support**. Award IQ combines
funding rules, structured operations, team evidence, and agency guidance into a cited assessment:
are we eligible, should we pursue the opportunity, and what must happen next?

All scenario records are synthetic. Recommendations and next actions require human approval.
The application does not approve funds, create tasks, send mail, book meetings, or submit applications.

## Scenarios

| Opportunity | What it demonstrates |
|---|---|
| **FO-2026-117** | Community-resilience grant closing December 16, 2026. Amendment 2 requires 25% local match and a regional partner. The $9M eligible-cost basis requires $2.25M match; $1.8M confirmed leaves a $450K gap. Proposed funds and a historic partner letter are not current commitments. |
| **FO-2026-204** | Ready comparator with supporting eligibility and match evidence; still not submitted. |
| **FO-2026-330** | Failed geography eligibility, demonstrating an evidence-backed negative finding. |

The hero scenario is pinned to **November 16, 2026**, not the machine's clock. Its recorded
`Pursue - pending` disposition is not an approval. The assessment shows current amendments,
confirmed versus proposed match, unresolved evidence, owners, deadlines, dependencies, and a
human-review action sequence.

## Sources and runtime modes

| Layer | Local walkthrough | Connected deployment |
|---|---|---|
| Fabric IQ | CSVs in `data/fabric/funding_ops` | Read-only, managed-identity SQL queries over the isolated funding lakehouse |
| Foundry IQ | Packaged funding documents | Azure AI Search knowledge-base retrieval; optional model-generated takeaway and explanation |
| Work IQ | Packaged proposal and reviewer evidence | Certificate-backed delegated OBO and scoped Work IQ MCP retrieval of configured synthetic M365 documents |
| External guidance | Packaged synthetic agency snapshot | Still packaged; not live web search |

Live transport does not make the fictional data real. The response exposes `mode`, `knowledgeMode`,
`workMode`, and `narrativeModel`. Financial calculations and recorded workflow status remain
deterministic. Enabled live-source or model failures produce explicit errors, not fixture fallback.
The streaming UI reports actual source activity, preserves completed source states on failure,
and shows numbered citations with expandable provenance.

## Run locally

Prerequisites: Python 3.12+ and Node.js 22+. No Azure credentials are needed.
From the repository root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services\api\requirements.lock.txt
Copy-Item services\api\.env.example services\api\.env
Set-Location apps\web
npm ci
Set-Location ..\..
.\scripts\dev.ps1
```

The launcher explicitly disables all live flags and browser Entra configuration for this process,
starts the API at `http://localhost:8000`, and runs Vite at `http://localhost:5173`.
The backend runs in a separate window. Stop that process after the walkthrough.
For other shells, configure the same values from `services/api/.env.example`, start
`python -m uvicorn app.main:app --app-dir services/api --port 8000`, and run `npm run dev`
from `apps/web`.

## Connected setup is operator-assisted

The supported infrastructure entry point is **`infra/funding.bicep`**, also selected by
`infra/azure.yaml`. CI runs secret scanning only; run application and infrastructure checks locally.
Read [deployment prerequisites](docs/deployment.md)
before running any provisioning helper.

Use a new Award IQ resource group, workspace, and lakehouse on an explicitly selected **existing
Fabric capacity**. Do not resize or replace that capacity, reuse another demo's lakehouse, or
overwrite another demo's resources. The loader refuses nonempty lakehouses and existing source
files; funding knowledge creation refuses existing index/source/base resources.

This is **not a complete one-command bootstrap**. `infra/funding.parameters.json` binds baseline
app/Fabric/Entra inputs but does not bind the optional intelligence or Work IQ parameters.
Operators must supply those explicitly and complete Entra registrations/consent, certificate and
Key Vault setup, Fabric workspace/lakehouse and SQL permissions, knowledge indexing, M365 document
placement/indexing, and identity verification. Model availability, regional capacity, preview API
support, and Work IQ billing/consent are prerequisites, not automated guarantees.

## Repository

| Path | Purpose |
|---|---|
| `apps/web` | Funding question, streaming progress, assessment and citations |
| `services/api/app` | Funding assessment, source adapters, authentication and certificate OBO |
| `data` | Funding fixtures, registry, ontology, generator and source documents |
| `agent/provisioning/live` | Explicit operator helpers for isolated funding setup and read-only inspection |
| `infra` | Funding app and optional intelligence infrastructure |
| `tools/validate_consistency.py` | Funding relationships, arithmetic, provenance and reproducibility |

Clinical routes, fixtures, UI, agent orchestration, legacy IaC, and the old promotional site
have been removed. There is only one application use case.

## Checks

```powershell
$env:PYTHONPATH = "services\api"
$python = ".\.venv\Scripts\python.exe"
& $python -m pytest services\api\tests agent\provisioning\live -q
& $python tools\validate_consistency.py
& $python -m pyright --pythonpath $python
az bicep build --file infra\funding.bicep --stdout
Set-Location apps\web
npm run lint -- --max-warnings 0
npm test
npm run build
```

Install `tools/requirements.lock.txt` into the same virtual environment for repository tooling. Checks do not require
cloud writes. Private keys, certificate bundles, credential caches, and local deployment outputs
are explicitly ignored; safe `.env.example` files and funding source JSON remain trackable.
Gitignore does not protect an already tracked secret: inspect staged changes before publishing.

See [API contract](docs/api-contract.md), [configuration](docs/configuration.md),
[architecture](docs/architecture.md), [limitations](docs/limitations.md), and
[security](docs/security.md). License and attribution are preserved in [LICENSE](LICENSE).
