# Award IQ synthetic funding operations

The deterministic generator in `generate.py` writes the CSV tables for three linked, synthetic
funding scenarios. The hero scenario is as of **2026-11-16**. Its deadline is **2026-12-16,
America/New_York**. Dates are ISO `YYYY-MM-DD`; timestamps use the adjacent timezone column.
Money is integer whole USD; percentages are decimal fractions such as `0.25`. Empty values mean
unknown/not recorded, never zero or a negative finding. Boolean values are lowercase `true`/`false`.

The hero $9,000,000 eligible-cost basis and $6,750,000 grant request are explicit fixture-design
assumptions (75% grant request / 25% local match), not inferred facts from the reference screenshots.
Eligible budget lines roll up exactly to $9,000,000. Amendment 2 yields $2,250,000 required match.
The unique 2026 capital-plan allocation of $1,800,000 is confirmed. The separate $450,000 reserve
candidate is proposed and excluded until Finance confirms it. `allocation_id` is the de-duplication
key, so repeated prose references never add money.

## Tables

| Table | Primary key and important fields | Semantics |
|---|---|---|
| `funding_opportunities` | `notice_id`; program/project/applicant/geography IDs; eligible applicant types/geographies; deadline/timezone, as-of date, eligible cost, requested amount, current amendment | One row per notice. `query_terms` drives deterministic notice selection; unknown portal requirements remain explicit. |
| `programs` | `program_id`; scoring objectives; source document ID | Grant program and its documented scoring alignment. |
| `projects` | `project_id`; notice/program/applicant/geography IDs; status | Proposal concept linked to its notice and applicant. |
| `organizations` | `organization_id`; type and geography ID | Applicant and partner organizations. |
| `geographies` | `geography_id`; geography type and eligible-area flag | Stable service-area references. |
| `amendments` | `amendment_id`; notice, version, published/effective dates, predecessor, changed conditions, match rate/basis, partner requirement, source document | The latest effective amendment on or before `as_of_date` controls. |
| `eligibility_criteria` | `criterion_id`; notice/amendment; type, rule, observed fact, status, evidence ID | Status is `met`, `not_met`, or `unknown`. Match and partner states are recalculated from source records. |
| `budget_lines` | `line_id`; notice/project; category, amount, currency, classification, document | `Eligible project cost` lines sum to the opportunity's eligible-cost basis. |
| `match_sources` | Unique `allocation_id`; notice/project, source, amount/currency, status, evidence date, owner/document, restrictions | Status is `Confirmed`, `Proposed`, or `Rejected`; only unique confirmed allocations reduce the gap. |
| `partners` | `partner_id`; partner organization, notice, region/type/qualification, commitment state, current letter/date, prior proposal, evidence | `Missing`, `Received`, `Declined`, and `Not required` are distinct; a prior letter is not current evidence. |
| `people` | `person_id`; display name, role/team | Owners and reviewers join by stable ID. |
| `prior_proposals` | `proposal_id`; current/prior notice, program/project, partner, evidenced outcome, lesson, letter/document | `Unknown` outcome stays unknown; no award probability is inferred. |
| `program_performance` | `metric_id`; program/project, baseline, actual, proposed target, period/unit/source | Actual and proposed target are separate; an empty actual is not zero. |
| `community_metrics` | `metric_id`; program/geography, value/unit/period, eligibility relevance, source | Synthetic community context, not individual-level eligibility. |
| `staff_workload` | `workload_id`; person/notice/team, capacity, commitments, availability exception, finish-by date, dependency IDs, evidence | Hours are synthetic planning estimates; leave is not a scheduled review. |
| `scheduling_slots` | `slot_id`; notice/reviewer/review IDs, start/end/timezone, state/purpose/dependency IDs/evidence | `Available` means a slot exists; it is not held, booked, or approval. |
| `approvals` | `approval_id`; notice/project/type/owner, state, decision/date/conditions/dependencies/evidence | `Pending` and `Approved` refer only to the named internal review; neither proves an award. |
| `submissions` | `submission_id`; notice/project/owner, pursuit and submission states, deadline, required artifacts, blockers, unknown requirements, dependency IDs | `Not submitted` is separate from pending pursuit and internal readiness. |
| `proposal_tasks` | `task_id`; notice, owner, state, due date, dependency IDs and supporting document IDs | Existing open tasks are represented as drafts in the UI and are never written to Planner/M365. |
| `source_documents` | `document_id`; notice, source/type, filename/version, publication/effective dates, supersession, summary | Stable IDs resolve to accessible synthetic documents or cached fixture JSON. |

## Join paths and precedence

- `funding_opportunities.notice_id` → program, project, amendments, criteria, budgets, match
  allocations, partners, approvals, schedule, workload, tasks, submissions, and source documents.
- `funding_opportunities.project_id` → `projects.project_id` → applicant organization/geography;
  `program_id` joins the program and its performance/community metrics.
- `partners.partner_org_id` → `organizations.organization_id`; prior-proposal and partner links use
  `proposal_id` / `historical_proposal_id`.
- `owner_id`, `reviewer_id`, and `required_owner_id` → `people.person_id`.
- Every `*_document_id` and `supporting_document_ids` value → `source_documents.document_id`.
  `supersedes` and amendment `predecessor_id` point to an older document/amendment version.
- Funding terms use the latest effective notice amendment. Match uses unique confirmed allocation
  rows. Workflow state uses the latest dated review/task/calendar record. Conflicts not resolved by
  these authorities are surfaced for human confirmation.

## Scenarios and safe interpretation

- `FO-2026-117`: conditional hero; 25% local match, missing current regional letter, and a pending
  human pursuit record.
- `FO-2026-204`: ready-to-submit comparator with confirmed match, approved partner waiver, and
  internal readiness approval. It remains unsubmitted and is not a funding award.
- `FO-2026-330`: comparator with a documented geography criterion that is not met; other criteria
  are not inferred.

Run `python data/fabric/funding_ops/generate.py` to regenerate the checked-in tables.
