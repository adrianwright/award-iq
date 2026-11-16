# Award IQ frontend

The React/Vite application provides an editable question, four-layer retrieval progress, and a
structured grant-readiness view. It renders current pursuit status, amendment and eligibility
findings, match arithmetic, unresolved partner evidence, task owners/deadlines, review timing, legal
availability, evidence citations, and trace steps.

All next actions are visually labeled `Drafted (not submitted)`. The UI distinguishes the grounded
recommendation from a human funding decision and says `Not submitted` for the application. Citations
open accessible synthetic Markdown documents using the API's evidence route.

The layout supports narrow screens and uses native form labels, status text, and alert semantics.
Run `npm test`, `npm run lint`, and `npm run build` in `apps/web`.
