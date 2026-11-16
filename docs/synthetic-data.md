# Synthetic funding data

All Award IQ scenario data is fictional and labeled synthetic. The fixed scenario date is
2026-11-16; the FO-2026-117 deadline is 2026-12-16. The grant data is original to this repository
and carries version/date provenance in its Markdown front matter and structured records.

The data includes a current Amendment 2 (effective 2026-10-28), versioned readiness and match memos,
2026-11-05 go/no-go review notes, 2026-11-09 proposal huddle notes, an older v1 tracker superseded by
v2, and the historical 2024 partner letter. The evidence differentiates confirmed match from
proposed sources, and the historic partner letter from a new required commitment.

The local external-evidence provider is an offline synthetic agency-guidance snapshot. Fixtures do
not indicate live Foundry IQ, Fabric IQ, Work IQ, agency, email, or Teams connections. No tenant is
seeded and no cloud resource is automatically provisioned.

Regenerate funding tables and validate the repository data with:

```bash
python data/fabric/funding_ops/generate.py
python tools/validate_consistency.py
```

The MIT license and original attribution notice remain in `LICENSE`.
