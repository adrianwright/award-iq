# Optional Fabric funding data load

The local Award IQ application does not need Azure credentials or any resource provisioning.
`load_fabric_lakehouse.py` and `provision_fabric_data_agent.ps1` now target the synthetic grant
tables under `data/fabric/funding_ops/`. They require operator-supplied workspace, Lakehouse,
Data Agent, and token values; neither is run by the local launcher.

The suggested resource slugs are `award-iq-fabric-funding-agent` and
`award_iq_fabric_funding_ops`. The funding ontology contract is
`data/ontology/funding_ontology.yaml`.

**Do not run `provision_all.ps1` or the remaining Foundry/Work IQ scripts as an Award IQ deployment.**
Those source-project provisioning scripts still contain clinical-domain assumptions and are not an
implemented live Award IQ stack. They do not provision resources automatically. A connected
deployment must first adapt and review the relevant Foundry knowledge-base, ontology, Work IQ, auth,
and security configuration for funding data.

The grant fixture collection remains synthetic. Uploading it is a separate, explicit operator
action; this repository never seeds a tenant or provisions cloud resources automatically.
