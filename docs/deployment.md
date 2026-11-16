# Award IQ Azure deployment

The funding deployment uses `infra/funding.bicep` (the entry point selected by
`infra/azure.yaml`). It provisions app resources in a new resource group independently from the existing
Fabric capacity: Container Apps, a private-pull container registry, a managed identity,
Static Web Apps, and monitoring. It does not create, resize, pause, or delete Fabric capacity,
or assign permissions to existing Search/Foundry resources.

With `enableFundingIntelligence=true`, it additionally creates a dedicated Basic Search service
and keyless Foundry account/project in the same resource group, with the selected model deployment.
The deployment uses GPT-5.6-luna (`2026-07-09`, GlobalStandard) by default; `fundingModelName` and
`fundingModelVersion` are explicit template parameters. Search Basic has a standing service cost;
agentic retrieval and model inference also incur usage charges. Semantic ranking uses its free
allowance and fails explicitly if that allowance is exhausted.
`fundingSearchLocation` can select a different supported region without moving the app or model.
This deployment uses Central US for Search because East US 2 rejected new Search provisioning
for lack of regional capacity; Foundry and the app remain in East US 2.

## Fabric isolation and loading

Create a dedicated Award IQ workspace on the chosen existing capacity, then a new lakehouse.
Do not point the seed loader at another demo's lakehouse. With the current `az` CLI identity,
obtain Fabric and Storage tokens into process environment variables `FABRIC_TOKEN` and
`ONELAKE_TOKEN`. Set `FABRIC_WS`, `FABRIC_LH`, and optionally `CSV_DIR`, then explicitly run
`agent/provisioning/live/load_fabric_lakehouse.py` from the repository root.

The loader refuses nonempty lakehouses before uploading anything, creates source files with
`If-None-Match: *`, and loads all 16 funding tables, including `source_documents`. It never uses
overwrite mode. Failures and incomplete operations stop the load; rerunning is not a destructive
reset mechanism. Keep existing demo workspaces, lakehouses, and tables untouched.

## Authentication and infrastructure

Use separate, single-tenant Entra registrations for the API and browser client. Expose the
API's delegated `access_as_user` scope with v2 access tokens, configure the SPA's exact HTTPS
redirect URI, and authorize the browser client for that scope. No client secret is needed.
Pass the API client ID as `apiAudience`, the SPA client ID as `webClientId`, and its fully
qualified scope as `webApiScope`.

Use the currently signed-in Azure CLI account to deploy `infra/funding.bicep` incrementally
into the new resource group. Supply the lakehouse's actual SQL connection string as
`fabricSqlServer`, its SQL database name as `fabricSqlDatabase`, both Fabric item IDs, the
tenant ID, and the existing capacity coordinates. For azd, these map to
`infra/funding.parameters.json`; explicitly set the subscription and new resource group.

The parameter file binds only baseline app/Fabric/Entra inputs. It does **not** bind
`enableFundingIntelligence`, model/region overrides, `enableFundingWork`, or Work IQ certificate
and document parameters. Supply these explicitly using an operator-reviewed parameter file or
ARM invocation. Entra registration/consent, certificate/Key Vault setup, Fabric bootstrap and
M365 document setup are manual prerequisites; `azd up` alone does not complete them.

Grant the new managed identity **Viewer** in the isolated Fabric workspace and Reader on
the capacity for its read-only status endpoint. The azd postprovision hook requests Viewer,
not Member. This does not grant data-write access or membership in other demo workspaces.

Build `services/api/Dockerfile` from the repository root, push it to the new registry, and
deploy that image to the new API Container App. The image includes Microsoft ODBC Driver 18.
Build the web app with the infrastructure's `VITE_*` outputs, then deploy `apps/web/dist`
to the new Static Web App. Never expose a web deployment token in logs or source control.

## Runtime guarantees and boundaries

The funding template sets `USE_LIVE_FABRIC=true`. Production requires
explicit Entra configuration, a managed identity, and valid Fabric SQL coordinates.
The API reads the allowlisted funding tables using a managed-identity SQL token, encrypted
connections with certificate verification, and read-only SELECT statements. Local operator
checks without a managed identity use `AzureCliCredential`, not another cached identity.
Each assessment uses one retrieved table set. JSON requests return 503 on Fabric read failures;
streaming requests emit an error and no final assessment. There is no CSV fallback.
The old assessment and cohort endpoints have been removed.

## Foundry IQ and model synthesis

The assessment leads with a generated takeaway and a question-specific explanation
(target: 100-150 words combined), key funding/deadline facts, unresolved eligibility conditions,
and one ordered action table. It does not display intermediate IQ responses, raw document
metadata, or duplicate task cards. Full retrieval grounding still reaches the final model;
the internal `retrievalContext` is excluded from the public assessment serialization.
Existing financial, recorded-status, and citation checks remain in force with no canned fallback.

Numbered citations open the original sources. Eligibility calculations, action dependencies,
source links, and technical provenance are collapsed by default. Retrieval progress remains
expanded while running or on failure, collapses after success, and focus moves to the result.
Printing produces the decision summary and action table without the question form, progress,
or technical details. These are synthetic records and **human review is required**, not already completed.

Enable the intelligence parameter when deploying infrastructure, then grant the current `az` operator
Search Service Contributor and Search Index Data Contributor on **only the new Search service**.
The API identity receives Search Index Data Reader and Cognitive Services OpenAI User; Search's
system identity receives Cognitive Services User on the new Foundry account. No API keys are used.

Using the same signed-in CLI identity, run this once from the repository root with the infrastructure
outputs:

```powershell
py -3.13 agent\provisioning\live\provision_funding_knowledge.py `
  --search-endpoint <SEARCH_ENDPOINT> --model-endpoint <FOUNDRY_ENDPOINT> `
  --model-deployment <MODEL_DEPLOYMENT> --model-name gpt-5.6-luna
```

The script indexes only funding documents named in `source_documents.csv`. It creates `award-iq-funding-docs`, `award-iq-funding-ks`, and `award-iq-funding-kb`.
Creation uses `If-None-Match: *`; an existing index/source/base stops provisioning rather than
overwriting it. A partially completed run must be inspected before resuming; never delete existing
demo resources to retry. No Fabric or M365 writes occur.

Deploy the updated API with `USE_LIVE_FOUNDRY=true`, `FOUNDRY_KS_NAME`, `FOUNDRY_KB_NAME`,
`SEARCH_ENDPOINT`, `SEARCH_API_VERSION=2026-08-01-preview`, `USE_LIVE_FUNDING_LLM=true`,
`FOUNDRY_ENDPOINT`, and `MODEL_DEPLOYMENT` (the funding template supplies these when enabled).
Do not direct traffic to that revision until knowledge provisioning succeeds.

Each assessment queries the actual knowledge-base retrieve API, filtered by notice and effective
date, including an exclusive supersession date. The current governing document must be retrieved.
Citation snippets come from returned source data, never local document reads. Citation links open
the packaged copy of the exact document uploaded during provisioning; the provenance labels that
copy explicitly. Unretrieved documents are not presented as live citations.

The final answer and bottom line use the real model's structured-output API over the reconciled
facts and evidence. Financial calculations and status fields remain deterministic. Responses carry
`knowledgeMode` and the actual returned `narrativeModel`; traces record live retrieval/model latency.
Unknown citations, changed dollar amounts, missing recorded status, source failures, model errors
and incomplete model output fail explicitly with 503 or an SSE error, never a canned answer.
These checks do not prove every generated statement correct; human review is still required.

## Funding Work IQ integration

The opt-in funding path forwards the authenticated API user's token to the existing certificate-backed
on-behalf-of client. Configure `enableFundingWork`, the API app client ID, the Key Vault URI and
certificate secret, and `workIqFundingDocumentUrls`: a JSON object mapping current funding document
IDs to their exact, non-token-bearing HTTPS SharePoint links. The certificate must be registered on
the API app, and its managed identity must be able to read the Key Vault secret. Set up and verify
these resources separately before enabling the flag.

The authenticated operator diagnostic `POST /api/workiq/check` exercises the same
certificate-backed OBO flow with a fixed acknowledgment-only prompt.
This check can run while `USE_LIVE_WORK=false`; configure the client ID and certificate settings
first. It does not verify document access or indexing and does not enable live funding retrieval.
It is not a separate user-facing assessment action. No access tokens or certificate material should
be copied into chat or logs.

After verifying document identities and configuring their canonical URLs, operators can call
the same authenticated diagnostic with one allowlisted `notice_id` at a time. It runs the normal
Fabric, Foundry, Work IQ and final-model assessment with live Work IQ enabled only for that explicit
request, leaving the global setting unchanged. A successful response requires live attributed Work IQ
evidence; it is not returned on source or model failure. This verifies the returned citations, not
that every configured file was indexed or cited.

The user-facing **Assess funding readiness** action always uses the configured IQ sources together.
With `USE_LIVE_WORK=true`, it includes delegated Work IQ in the same Fabric/Foundry assessment and
final model context; there is no separate Work IQ button or automatic packaged Work fallback.
The SSE stream reports each source when its operation actually starts and finishes. A later source
failure preserves earlier retrieval results; the browser marks sources that never started as skipped.
Fabric first resolves the authoritative notice, amendment and document scope. Foundry IQ, Work IQ and
packaged external guidance then load concurrently before the final assessment is synthesized.
The retrieval panel uses source icons, activity indicators, elapsed times and returned evidence
counts. It distinguishes retrieval from final answer generation, preserves successful source states
on failure, and respects reduced-motion preferences. No percentage or simulated progress is shown.

Work IQ `WorkIQAgent.Ask` requires tenant admin consent and a Copilot Studio usage-based billing plan
with an Azure subscription and resource group, with the user assigned to the plan. Microsoft describes this
delegated permission as including **read and write** access to Microsoft 365 resources accessible to
Work IQ agents on behalf of that user; it is broader than this application's read-only use. Obtain
the administrator's approval before granting it. Do not confuse this with an application permission.

Funding uses the public-preview MCP `retrieve` tool at `WORK_IQ_MCP_ENDPOINT` (default
`https://workiq.svc.cloud.microsoft/mcp`), not a synthesized A2A answer. It discovers the live tool
schema and requests the `grounding` strategy with `OneDriveAndSharePoint.items_by_url` restricted to
configured current document URLs for the selected notice. The same delegated `WorkIQAgent.Ask`
permission and certificate-backed OBO flow are used; no Graph permission is added.

The adapter reads `structuredContent["application/vnd.ms-workiq.retrieval"].results`, binds each
result's Markdown to its own returned URL and citation ID, and retains the sensitivity display label.
Only completed retrievals with explicitly allowed content protection are accepted. Source matching
allows canonical URLs or a unique, case-insensitive filename on the configured SharePoint host.
Filenames can come from the returned URL path, a viewer link's `file` parameter, or returned document
title metadata. This relaxed demo rule can match a same-named copy elsewhere on that host; it is not
proof of folder isolation. Filename matches retain the actual returned source link for review.
Duplicate filename matches, unrelated hosts, and known conflicting identities are rejected.
The `workIqFundingDocumentIdentities` deployment parameter supplies
`WORK_IQ_FUNDING_DOCUMENT_IDENTITIES`, binding document IDs to setup-verified
`webUrl`, `driveId` and `itemId` values, allowing alternate viewer links without filename metadata.
Configure it when Work IQ returns opaque SharePoint viewer links; URL or filename matching alone
cannot identify those links. Obtain it with the read-only inspector's `--identity-output` option.
Rejected sources produce bounded structural diagnostics, not document content or access tokens.
Missing evidence, unknown citations, partial results and service errors stop the
assessment without switching tools, strategies or sources. Generated grounding is not a verbatim
document excerpt; claims still require human review. The broad delegated permission remains broader
than this per-request source scope. M365 indexing and retrieval availability must be verified against
the actual tenant. No live Work IQ configuration or document set is included by default.

See Microsoft's [Work IQ retrieve contract](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/retrieve).

The data remains **synthetic**, even when stored and queried through real services. External
guidance remains packaged; until Work IQ is configured, proposal workflow records are stored in
Fabric and packaged documents, not synchronized with M365.
The application never approves funding, writes tasks, sends mail, books meetings, or submits
applications.

The root README's local mock walkthrough remains available without Azure credentials.
