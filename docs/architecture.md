# Award IQ architecture

```text
React/Vite + optional Entra sign-in
  -> FastAPI funding REST/SSE + bearer validation
    -> Fabric funding records: local CSVs OR live managed-identity SQL
    -> Foundry funding evidence: packaged OR live knowledge-base retrieval
    -> Work funding evidence: packaged OR delegated certificate-OBO MCP retrieval
    -> External guidance: packaged synthetic snapshot
    -> deterministic calculations/status + optional grounded model narrative
    -> cited human-review assessment
```

Fabric resolves the authoritative opportunity, amendment, and source-document scope first.
Foundry, Work IQ and external guidance then retrieve concurrently. SSE reports actual source
start/completion/failure and returns a final assessment only on success. Live sources never fall
back to packaged data on failure.

FO-2026-117 is pinned to November 16, 2026; FO-2026-204 and FO-2026-330 are ready and failed
comparators. Current amendments, confirmed match and recorded approvals govern the result.
Question-specific narrative does not change arithmetic, citations, or the recorded human status.

The app is read-only decision support. Provisioning helpers are separate, explicit operator actions,
not part of an assessment. Connected services hold synthetic records in isolated Award IQ resources,
using an existing Fabric capacity without overwriting other demos.
