# Award IQ architecture

The local, deterministic funding assessment is an end-to-end vertical slice:

```text
React/Vite -> FastAPI REST/SSE -> synthetic grant assessment
                                  +-> Foundry IQ funding knowledge fixtures
                                  +-> Fabric IQ funding operations tables
                                  +-> Work IQ proposal and calendar evidence
                                  `-> external synthetic guidance snapshot
```

The UI sends free-form questions to `/api/funding/ask/stream`. The backend emits retrieval
progress, composes an assessment from the pinned FO-2026-117 scenario, and returns source citations
that resolve through the allowlisted evidence endpoint. The non-streaming equivalent is
`/api/funding/ask`.

The scenario has an explicit 2026-11-16 as-of date. It does not derive fixed demo facts from the
current clock. Latest effective Amendment 2 governs, confirmed funds alone reduce the match gap,
and the recorded human status remains `Pursue - pending`. No output is an approval or a write action.

The repository retains optional integration/auth scaffolding from its source project. Local Award IQ
does not call live providers, provision Azure resources, seed a tenant, or use M365 fixtures as live
data. See [limitations](limitations.md) and [security](security.md) before considering any
connected deployment.
