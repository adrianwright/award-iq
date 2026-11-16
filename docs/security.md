# Award IQ security boundaries

This is synthetic funding decision support, not a production grant-management security guarantee.
Report vulnerabilities privately as described in [SECURITY.md](../SECURITY.md).

Production funding assessments and Work IQ diagnostics require an Entra bearer token validated for
signature, issuer, tenant, audience, lifetime and delegated scope. Anonymous fixture access is limited
to explicitly local/test configuration with no live components. CORS permits configured origins only;
the browser sends bearer headers, not credentialed cookies.

Fabric uses encrypted, certificate-verified SQL connections, managed-identity tokens and allowlisted
read-only SELECTs. The isolated workspace identity is a Viewer. Capacity status is read-only.
Search/model access uses identity-based roles on the new funding resources, not shared demo services.

Work IQ uses per-request delegated OBO with a certificate, never a client-secret fallback. Production
loads the PFX secret from Key Vault with managed identity and caches the converted certificate briefly.
The signed-in user's access boundaries still apply. The delegated `WorkIQAgent.Ask` permission is
broader than this application's read-only use and requires explicit administrator approval and billing.
Scoped retrieval, protection checks and citation matching are not substitutes for tenant permissions.
Same-filename matching on the configured host is a demo convenience, not proof of folder isolation.

Retrieved documents and user questions are untrusted. Model output is constrained by structured
financial/status/citation checks, but those checks cannot prove every sentence correct. Human review
is mandatory. No assessment writes tasks, sends messages, books meetings, approves funds or submits
applications. Live errors stop the assessment; no synthetic success replaces a failed live source.

Health and capacity status are public metadata routes. The evidence endpoint is also public and
serves only allowlisted packaged synthetic documents. Do not add private documents to that package
or container image. Live M365 citation URLs rely on the user's existing access.

Keep tokens, private keys, certificate bundles, credential caches and deployment outputs out of Git
and logs. Explicit ignore patterns supplement review; they do not untrack existing secrets.
Setup helpers must target dedicated Award IQ resources. Never point them at another demo's resources
or treat a partial provisioning failure as permission to delete or overwrite existing data.
