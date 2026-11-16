# Award IQ Fabric funding operations tables

The deterministic generator in this directory writes synthetic CSV fixtures for the FO-2026-117
scenario. IDs are stable and retain the notice/task identifiers used in source documents and
citations. Amounts are whole US dollars. Dates are ISO `YYYY-MM-DD`; the scenario as-of date is
2026-11-16 and the deadline is 2026-12-16.

| Table | Grain and key | Purpose |
|---|---|---|
| `funding_opportunities` | One row per notice (`notice_id`) | Deadline, fixed as-of date, eligible-cost basis, and current status |
| `amendments` | One row per amendment (`notice_id`, `amendment`) | Effective-version precedence and changed match/partner terms |
| `approvals` | One row per review record (`approval_id`) | Historical human disposition; not an approval event |
| `budget_lines` | One row per planning budget line (`line_id`) | $9,000,000 cost base and derived 25% required match |
| `match_sources` | One row per source (`source_id`) | Confirmed vs proposed sources; only confirmed values count |
| `eligibility_criteria` | One row per criterion (`criterion_id`) | Grounded applicant, match, and partner findings |
| `partners` | One row per notice/partner (`partner_id`) | Current commitment status and historical lead |
| `people` | One row per owner/reviewer (`person_id`) | Proposal team identity and role |
| `proposal_tasks` | One row per task (`task_id`) | Task owner, open state, and due date |
| `scheduling_slots` | One row per review slot (`slot_id`) | Review window and explicit timezone |
| `staff_workload` | One row per unavailable staff member/notice | Legal availability and required finish-by date |
| `submissions` | One row per application (`submission_id`) | Submission status; current value is Not submitted |
| `community_metrics` | One row per metric (`metric_id`) | Synthetic population/service-area context |
| `prior_proposals` | One row per prior proposal (`proposal_id`) | Historical partner relationship evidence |
| `program_performance` | One row per measure (`program_id`, `measure`) | Synthetic service/program context |

Required local match is calculated as `total eligible project costs × current effective amendment
match rate`: `$9,000,000 × 25% = $2,250,000`. The confirmed 2026 capital-plan source is $1,800,000,
so the gap is $450,000. A $450,000 capital-reserve candidate is explicitly Proposed and must not be
added to confirmed match.

Run `python data/fabric/funding_ops/generate.py` to regenerate the tables.
