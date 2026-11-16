# Award IQ configuration

`services/api/app/config.py` is the runtime contract. Unknown environment settings are ignored.
Anonymous fixture mode requires an explicit local/development/test `APP_ENVIRONMENT` and all four
live flags disabled. Production defaults to authenticated live operation and rejects missing or
placeholder values before startup.

| Setting or feature | Required configuration |
|---|---|
| Local fixtures | `APP_ENVIRONMENT=development`; `USE_LIVE_FABRIC`, `USE_LIVE_FOUNDRY`, `USE_LIVE_FUNDING_LLM`, `USE_LIVE_WORK` all false |
| Connected funding | `USE_LIVE_FABRIC=true`, `AZURE_TENANT_ID`, `API_AUDIENCE`, `API_REQUIRED_SCOPE`, `AZURE_CLIENT_ID`, `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_ID`, `FABRIC_SQL_SERVER`, `FABRIC_SQL_DATABASE` |
| Foundry IQ | `USE_LIVE_FOUNDRY=true`, `SEARCH_ENDPOINT`, `FOUNDRY_KB_NAME`, `FOUNDRY_KS_NAME`, compatible `SEARCH_API_VERSION` (funding IaC uses `2026-08-01-preview`) |
| Model synthesis | `USE_LIVE_FUNDING_LLM=true`, live Foundry IQ, `FOUNDRY_ENDPOINT`, `MODEL_DEPLOYMENT` |
| Work IQ | `USE_LIVE_WORK=true`, `WORK_IQ_CLIENT_ID`, `WORK_IQ_ENDPOINT`, `WORK_IQ_SCOPE`, `WORK_IQ_FUNDING_DOCUMENT_URLS` |
| Production Work IQ certificate | `WORK_IQ_KEY_VAULT_URL`, `WORK_IQ_CLIENT_CERTIFICATE_SECRET_NAME`; managed identity must read the certificate secret |
| Local live Work IQ certificate | `WORK_IQ_CLIENT_CERTIFICATE`, `WORK_IQ_CLIENT_CERTIFICATE_THUMBPRINT`; optional `WORK_IQ_CLIENT_PUBLIC_CERTIFICATE` |
| Work IQ retrieval | `WORK_IQ_MCP_ENDPOINT`; optional verified `WORK_IQ_FUNDING_DOCUMENT_IDENTITIES` for opaque viewer links |
| Optional capacity status | `AZURE_SUBSCRIPTION_ID`, `FABRIC_CAPACITY_RG`, `FABRIC_CAPACITY_NAME` |
| API origins and fixtures | `CORS_ORIGINS` (comma-separated), `DATA_DIR` (defaults to repository `data`) |
| Browser build | `VITE_API_BASE_URL`, `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_CLIENT_ID`, `VITE_API_SCOPE`; optional `VITE_REDIRECT_URI` |

`WORK_IQ_FUNDING_DOCUMENT_URLS` maps document IDs to exact non-token-bearing HTTPS SharePoint links.
The identity map binds IDs to `webUrl`, `driveId`, and `itemId`; obtain it using the read-only inspector.
Do not treat a connection-check acknowledgment as proof of document access.

The browser calls the API directly for SSE; a buffering proxy prevents incremental progress.
Never put credentials in `VITE_*` variables: they are public build-time values.

`infra/funding.parameters.json` is a baseline mapping, not a fully configured live deployment.
Optional intelligence and Work IQ parameters must be supplied separately after their prerequisites
are satisfied. See [deployment](deployment.md) for permissions, isolation, costs and setup limits.
