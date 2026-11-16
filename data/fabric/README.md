# Fabric IQ funding operations

The active funding tables are generated in `funding_ops/`. See
[`funding_ops/data_dictionary.md`](funding_ops/data_dictionary.md) and
[`../ontology/funding_ontology.yaml`](../ontology/funding_ontology.yaml) for the table schemas,
relationships, and invariants.

```bash
python data/fabric/funding_ops/generate.py
```

The 15 generated tables cover notice/amendment state, eligibility, budgets, confirmed and proposed
match, partners, people, approvals, workflow tasks, calendars, and submissions. The recommended
platform dataset name is `award_iq_fabric_funding_ops`; the sample tables are synthetic and do not
cause an Azure resource to be provisioned.

The old clinical table generator is retained for source-history compatibility but does not feed the
Award IQ frontend or funding API.
