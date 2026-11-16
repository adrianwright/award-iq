# Award IQ operator helpers

These are explicit operator actions, not a complete bootstrap or part of the local walkthrough.
See [deployment prerequisites](../../../docs/deployment.md) before running them.

| Helper | Scope |
|---|---|
| `load_fabric_lakehouse.py` | Loads 16 runtime funding tables into a new empty isolated lakehouse. Refuses existing tables and source files; never overwrites. |
| `provision_funding_knowledge.py` | Creates funding-only Search index, knowledge source and base using explicit endpoints. Refuses existing resources. |
| `inspect_funding_work_documents.py` | Read-only M365 metadata/identity inspection with an explicitly consented setup client and encrypted local token cache. |
| `grant_app_identity_fabric.ps1` | Grants the new API identity workspace Viewer and read-only capacity status access, using explicit resource coordinates. |
| `deploy_web.ps1` | Builds and deploys to an explicitly selected Static Web App after Entra and API configuration. |

The funding runtime reads Fabric SQL directly; no Fabric Data Agent or specialist-agent deployment
is required. Old clinical provisioning, M365 seeding and teardown scripts are removed.

Supply Entra registrations/consent, certificate/Key Vault access, Fabric workspace/lakehouse and
SQL permissions, knowledge indexing, and synthetic M365 documents separately. Reuse only the
selected capacity, not another demo's workspace or data. No helper runs automatically in local mode.
