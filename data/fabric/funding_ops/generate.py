from __future__ import annotations

import csv
from pathlib import Path


TABLES: dict[str, tuple[list[str], list[list[str]]]] = {
    "funding_opportunities": (
        ["notice_id", "title", "agency", "deadline", "as_of_date", "total_project_cost", "match_rate", "match_required", "status"],
        [["FO-2026-117", "Community Resilience Infrastructure Grant", "Federal Resilience Agency", "2026-12-16", "2026-11-16", "9000000", "0.25", "2250000", "Open"]],
    ),
    "amendments": (
        ["notice_id", "amendment", "published_date", "effective_date", "status", "match_rate", "regional_partner_required", "supersedes"],
        [["FO-2026-117", "1", "2026-09-10", "2026-09-10", "Superseded", "0.20", "false", ""],
         ["FO-2026-117", "2", "2026-10-28", "2026-10-28", "Current", "0.25", "true", "1"]],
    ),
    "eligibility_criteria": (
        ["criterion_id", "notice_id", "criterion", "status", "evidence_id"],
        [["FO-2026-117-ELIG-01", "FO-2026-117", "Eligible local public applicant", "met", "award-iq-foundry-applicant-eligibility-v1"],
         ["FO-2026-117-ELIG-02", "FO-2026-117", "Regional partner commitment letter", "uncertain", "award-iq-foundry-amendment-2-v1"],
         ["FO-2026-117-ELIG-03", "FO-2026-117", "Required 25% local match confirmed", "uncertain", "award-iq-foundry-match-policy-v1"]],
    ),
    "match_sources": (
        ["source_id", "notice_id", "source", "amount", "status", "owner_id", "evidence_id"],
        [["MATCH-2026-CAPITAL", "FO-2026-117", "2026 capital plan", "1800000", "Confirmed", "FIN-02", "award-iq-foundry-match-memo-v2"],
         ["MATCH-RESERVE-CANDIDATE", "FO-2026-117", "Capital reserve", "450000", "Proposed", "FIN-02", "award-iq-work-match-huddle-v2"]],
    ),
    "partners": (
        ["partner_id", "notice_id", "name", "current_commitment", "historical_evidence"],
        [["PARTNER-RTA", "FO-2026-117", "Regional Transit Authority", "Not received", "award-iq-work-prior-proposal-2024-v1"]],
    ),
    "people": (
        ["person_id", "name", "role", "email"],
        [["PM-01", "Jordan Lee", "Proposal Manager", "jordan.lee@example.invalid"],
         ["FIN-02", "Maria Santos", "Finance", "maria.santos@example.invalid"],
         ["EXEC-01", "Dr. Elena Ruiz", "Executive Reviewer", "elena.ruiz@example.invalid"],
         ["LEGAL-01", "Sam Patel", "Legal", "sam.patel@example.invalid"]],
    ),
    "approvals": (
        ["approval_id", "notice_id", "review_date", "decision", "conditions", "record_type"],
        [["REVIEW-FO-2026-117-2026-11-05", "FO-2026-117", "2026-11-05", "Pursue - pending", "Match confirmation and partner commitment letter", "Recorded review; not an approval"]],
    ),
    "budget_lines": (
        ["line_id", "notice_id", "basis", "amount", "classification"],
        [["BUDGET-FO-2026-117-TOTAL", "FO-2026-117", "Total eligible project costs", "9000000", "Planning basis"],
         ["BUDGET-FO-2026-117-MATCH", "FO-2026-117", "25% local match of total eligible project costs", "2250000", "Required match"]],
    ),
    "community_metrics": (
        ["metric_id", "notice_id", "metric", "value", "as_of_date"],
        [["METRIC-FO-2026-117-01", "FO-2026-117", "Priority service-area population", "18400", "2026-10-31"]],
    ),
    "prior_proposals": (
        ["proposal_id", "notice_id", "year", "partner_id", "evidence_id"],
        [["PR-2024-RESILIENCE", "FO-2026-117", "2024", "PARTNER-RTA", "award-iq-work-prior-proposal-2024-v1"]],
    ),
    "program_performance": (
        ["program_id", "notice_id", "measure", "value", "as_of_date"],
        [["PROGRAM-RESILIENCE", "FO-2026-117", "Projects delivered on schedule", "8/10", "2026-10-31"]],
    ),
    "scheduling_slots": (
        ["slot_id", "notice_id", "reviewer_id", "date", "start_time", "end_time", "timezone", "status"],
        [["SLOT-EXEC-2026-1119", "FO-2026-117", "EXEC-01", "2026-11-19", "10:00", "11:00", "America/Los_Angeles (PST, UTC-08:00)", "Available"]],
    ),
    "staff_workload": (
        ["person_id", "notice_id", "unavailable_from", "unavailable_through", "work_must_finish_by"],
        [["LEGAL-01", "FO-2026-117", "2026-11-23", "2026-11-27", "2026-11-20"]],
    ),
    "submissions": (
        ["submission_id", "notice_id", "status", "submitted_at"],
        [["SUBMISSION-FO-2026-117", "FO-2026-117", "Not submitted", ""]],
    ),
    "proposal_tasks": (
        ["task_id", "notice_id", "description", "owner_id", "status", "due_date"],
        [["TASK-117-MATCH", "FO-2026-117", "Confirm capital-reserve match source", "FIN-02", "Open", "2026-11-18"],
         ["TASK-117-PARTNER", "FO-2026-117", "Obtain current regional-partner commitment letter", "PM-01", "Open", "2026-11-20"]],
    ),
}


def generate(output_dir: Path | None = None) -> None:
    directory = output_dir or Path(__file__).resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    for name, (headers, rows) in TABLES.items():
        with (directory / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(headers)
            writer.writerows(rows)


if __name__ == "__main__":
    generate()
