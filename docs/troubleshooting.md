# Award IQ troubleshooting

| Symptom | Check |
|---|---|
| Startup `SettingsConfigurationError` | Supply all connected prerequisites, or explicitly select development mode with all four live flags false. The local launcher overrides live flags. |
| 401/403 | API audience, tenant, delegated scope, token expiry, SPA redirect URI and consent. Never paste tokens into logs. |
| Fabric 503 | Capacity state, isolated workspace Viewer/SQL access, SQL server/database and ODBC Driver 18. Do not enable CSV fallback to hide a live error. |
| Foundry 503 | Funding knowledge provisioning, endpoint/API version, retrieval scope, identity roles, model deployment/quota. A current governing document must be retrieved. |
| Work IQ failure | Certificate registration and Key Vault access, delegated permission/consent, billing, configured document URLs/identities and actual indexing. The acknowledgment check does not verify documents. |
| Progress appears all at once | Use the direct API URL in `VITE_API_BASE_URL`; buffering proxies can suppress SSE progress. |
| Data consistency failure | Run `python tools/validate_consistency.py`; inspect source relationships and generator differences before regenerating fixtures. |
| Provisioning refuses existing content | Inspect the partial run and target identity. Do not delete another demo's resources or overwrite its lakehouse to retry. |

See [deployment](deployment.md) for supported setup and [configuration](configuration.md) for settings.
