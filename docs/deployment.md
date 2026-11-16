# Award IQ deployment status

The supported walkthrough is local deterministic mock mode using checked-in synthetic funding
fixtures. Follow the root README; it requires neither Azure credentials nor network-dependent
providers.

Award IQ's grant operations are structurally represented in the Fabric funding tables, and the
optional `load_fabric_lakehouse.py` / `provision_fabric_data_agent.ps1` path targets those tables
only when an operator explicitly invokes it with their own resources and tokens.

**A complete connected Award IQ deployment is not implemented.** The remaining source-project
Foundry, Work IQ, and top-level provisioning paths retain clinical-domain assumptions and must not
be treated as Award IQ deployment instructions. Do not execute them for this scenario. The local
application uses synthetic Foundry/Work/external evidence fixtures, not tenant connections.

There are no automatic provisioning, tenant-seeding, task-write, email, calendar-write, or
application-submission operations.
