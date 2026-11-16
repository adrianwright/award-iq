# ADR 0002: Delegated Work IQ authentication boundary

## Decision

Award IQ uses separate single-tenant SPA and API Entra registrations. MSAL React acquires the API's
delegated scope; the API validates issuer, signature, tenant, audience, expiry and scope.
The backend exchanges the user's assertion through certificate-backed OBO for Work IQ access.

Production uses managed identity to read the exportable certificate's PFX secret from Key Vault.
The certificate is converted to MSAL's PEM representation and briefly cached. Refresh failures use
the last known certificate with retry backoff; there is no client-secret fallback. IDs, certificate
names, vault URI and scopes are operator settings, not committed credentials.

| Route | Policy |
|---|---|
| `POST /api/funding/ask` and `/api/funding/ask/stream` | Authenticated except explicit offline local/test mode |
| `POST /api/workiq/check` | Signed-in user required, including local mode |
| `GET /healthz`, `/api/fabric/status` | Public, bounded operational metadata |
| `GET /api/evidence/doc` | Public, allowlisted packaged synthetic documents only |

Funding evidence uses scoped Work IQ MCP retrieval. The diagnostic acknowledgment uses A2A but
does not prove document access. An explicit notice diagnostic runs the normal assessment with Work IQ
enabled for that request only. Failed source access stops the assessment, with no fixture fallback.

## Consequences

Consent, certificate registration, Key Vault permissions, user billing and document indexing are manual
prerequisites. The delegated permission is broader than this app's read-only use; administrators must
approve it knowingly. See [deployment](../deployment.md) for source matching limitations and setup.
