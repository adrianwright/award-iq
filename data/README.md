# Award IQ synthetic data

The active funding package contains three linked scenarios. Hero notice FO-2026-117 is pinned to
2026-11-16 and deadline 2026-12-16 America/New_York; dates never float with the machine's clock.
FO-2026-204 is ready to submit for internal review, while FO-2026-330 fails the evidenced geography
criterion.

| Directory | Role |
|---|---|
| `foundry_docs/` | Funding notice, amendments, applicant and match policies, agency guidance, and approval policy |
| `fabric/funding_ops/` | Deterministic structured grant tables, generator, and data dictionary |
| `ontology/funding_ontology.yaml` | Funding entities, relationships, and evaluation invariants |
| `work/` | Proposal huddle, decision minutes, versioned readiness trackers/memos, historical partner evidence |
| `web/` | Offline synthetic external agency-guidance snapshot |

The hero $9M eligible-cost basis and $6.75M requested grant are documented synthetic assumptions.
Amendment 2 requires $2.25M match; the $1.8M confirmed capital-plan allocation leaves a $450K gap.
The proposed reserve is excluded until Finance confirmation. The RTA's 2024 letter is a historical
lead, not a current commitment.

The clinical corpus and generator are retained for source-history compatibility only; they do not
feed the Award IQ UI or `/api/funding/*` routes.

Regenerate funding tables and validate consistency:

```bash
python data/fabric/funding_ops/generate.py
python tools/validate_consistency.py
```
