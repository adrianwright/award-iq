# Award IQ synthetic data

The active scenario is the fictional FO-2026-117 Community Resilience Infrastructure Grant.
Scenario date and deadline are pinned (2026-11-16 and 2026-12-16); they never float with the
machine's current date.

| Directory | Role |
|---|---|
| `foundry_docs/` | Funding notice, amendments, applicant and match policies, agency guidance, and approval policy |
| `fabric/funding_ops/` | Deterministic structured grant tables, generator, and data dictionary |
| `ontology/funding_ontology.yaml` | Funding entities, relationships, and evaluation invariants |
| `work/` | Proposal huddle, decision minutes, versioned readiness trackers/memos, historical partner evidence |
| `web/` | Offline synthetic external agency-guidance snapshot |

The required match is computed as 25% of $9,000,000 total eligible costs ($2,250,000). The confirmed
2026 capital-plan amount is $1,800,000, leaving a $450,000 gap. Proposed funds do not count as
confirmed. The Regional Transit Authority's 2024 letter is a historical lead, not a current letter.

The clinical corpus and generator are retained for source-history compatibility only; they do not
feed the Award IQ UI or `/api/funding/*` routes.

Regenerate funding tables and validate consistency:

```bash
python data/fabric/funding_ops/generate.py
python tools/validate_consistency.py
```
