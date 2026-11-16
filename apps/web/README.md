# Award IQ web application

React/Vite frontend for synthetic grant eligibility and funding-readiness review. It supports free
form funding questions, streams Foundry IQ/Fabric IQ/Work IQ/external evidence progress, and renders
decision conditions, match arithmetic, tasks, scheduling constraints, source citations, and trace.

Local development: `npm ci && npm run dev` from this directory. The Vite proxy forwards API requests
to the local FastAPI service. `npm test`, `npm run lint`, and `npm run build` run the configured
frontend checks.

All next actions are clearly marked `Drafted (not submitted)`. The UI does not approve funding,
create tasks, schedule meetings, or submit applications.
