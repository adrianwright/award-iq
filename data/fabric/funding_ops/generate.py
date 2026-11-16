from __future__ import annotations

import csv
from pathlib import Path


TABLES: dict[str, tuple[list[str], list[list[str]]]] = {
    "funding_opportunities": (
        ["notice_id", "program_id", "project_id", "applicant_org_id", "geography_id", "title", "agency", "program_purpose", "eligible_applicant_types", "eligible_geographies", "applicant_type", "applicant_geography", "deadline", "deadline_timezone", "as_of_date", "total_eligible_cost", "requested_amount", "project_cost_basis", "current_amendment_id", "status", "query_terms", "submission_requirements", "unknown_requirements"],
        [
            ["FO-2026-117", "PROGRAM-RESILIENCE", "PROJECT-RESILIENCE-2026", "ORG-NORTHSTAR", "GEO-NORTHSTAR-DISTRICT", "Community Resilience Infrastructure Grant", "Federal Resilience Agency", "Improve infrastructure resilience and continuity of essential community services.", "Local public entity", "Northstar Resilience District", "Local public entity", "Northstar Resilience District", "2026-12-16", "America/New_York", "2026-11-16", "9000000", "6750000", "Synthetic fixture-design assumption: eligible project costs are split between 75% grant request and 25% local match.", "AMD-FO117-02", "Open", "hero;community resilience;infrastructure;FO-2026-117", "Current partner commitment letter; confirmed local match; legal/procurement review; authorized final approval; application package", "Confirm any portal-specific attachments and certifications against the live notice before submission."],
            ["FO-2026-204", "PROGRAM-HEAT-READY", "PROJECT-HEAT-READY-2026", "ORG-RIVERBEND", "GEO-RIVERBEND-CITY", "Heat-Ready Community Facilities Grant", "State Climate Resilience Office", "Increase heat safety at public facilities serving high-risk residents.", "Local public entity", "Riverbend City", "Local public entity", "Riverbend City", "2026-12-10", "America/New_York", "2026-11-16", "1000000", "900000", "Synthetic comparator: $900,000 requested grant plus $100,000 confirmed local match.", "AMD-FO204-01", "Open", "ready comparator; fully ready; heat-ready; FO-2026-204", "Confirmed local match; approved partner waiver; internal readiness approval; application package", "Confirm portal-specific attachments before submission."],
            ["FO-2026-330", "PROGRAM-RURAL-ACCESS", "PROJECT-RURAL-ACCESS-2026", "ORG-NORTHSTAR", "GEO-NORTHSTAR-DISTRICT", "Rural Access Infrastructure Grant", "Federal Rural Services Agency", "Expand essential services in designated rural counties.", "Local public entity", "Pine County Rural Service Area", "Local public entity", "Northstar Resilience District", "2027-01-15", "America/New_York", "2026-11-16", "2000000", "1800000", "Synthetic comparator: $1,800,000 requested grant plus $200,000 confirmed local match.", "AMD-FO330-01", "Open", "failed eligibility; ineligible comparator; rural access; FO-2026-330", "Eligible rural geography; local match; application package", "Confirm portal-specific attachments before submission."],
        ],
    ),
    "programs": (
        ["program_id", "title", "agency", "scoring_objectives", "evidence_document_id"],
        [
            ["PROGRAM-RESILIENCE", "Community Resilience Infrastructure", "Federal Resilience Agency", "Service continuity for underserved communities; infrastructure resilience.", "DOC-FO117-NOTICE"],
            ["PROGRAM-HEAT-READY", "Heat-Ready Community Facilities", "State Climate Resilience Office", "Heat safety and public access for high-risk residents.", "DOC-FO204-TERMS"],
            ["PROGRAM-RURAL-ACCESS", "Rural Access Infrastructure", "Federal Rural Services Agency", "Essential services in designated rural areas.", "DOC-FO330-TERMS"],
        ],
    ),
    "projects": (
        ["project_id", "notice_id", "program_id", "applicant_org_id", "geography_id", "title", "status"],
        [
            ["PROJECT-RESILIENCE-2026", "FO-2026-117", "PROGRAM-RESILIENCE", "ORG-NORTHSTAR", "GEO-NORTHSTAR-DISTRICT", "Northstar Resilience Infrastructure Plan", "Proposed"],
            ["PROJECT-HEAT-READY-2026", "FO-2026-204", "PROGRAM-HEAT-READY", "ORG-RIVERBEND", "GEO-RIVERBEND-CITY", "Riverbend Heat-Ready Facilities", "Proposed"],
            ["PROJECT-RURAL-ACCESS-2026", "FO-2026-330", "PROGRAM-RURAL-ACCESS", "ORG-NORTHSTAR", "GEO-NORTHSTAR-DISTRICT", "Northstar Rural Access Concept", "Proposed"],
        ],
    ),
    "organizations": (
        ["organization_id", "name", "organization_type", "geography_id"],
        [
            ["ORG-NORTHSTAR", "City of Northstar", "Local public entity", "GEO-NORTHSTAR-DISTRICT"],
            ["ORG-RIVERBEND", "Riverbend City", "Local public entity", "GEO-RIVERBEND-CITY"],
            ["ORG-RTA", "Regional Transit Authority", "Regional public authority", "GEO-NORTHSTAR-DISTRICT"],
            ["ORG-RIVERBEND-PHD", "Riverbend Public Health District", "Public health district", "GEO-RIVERBEND-CITY"],
        ],
    ),
    "geographies": (
        ["geography_id", "name", "geography_type", "eligible_area"],
        [
            ["GEO-NORTHSTAR-DISTRICT", "Northstar Resilience District", "Service district", "true"],
            ["GEO-RIVERBEND-CITY", "Riverbend City", "Municipality", "true"],
            ["GEO-PINE-RURAL", "Pine County Rural Service Area", "Rural service area", "true"],
        ],
    ),
    "amendments": (
        ["amendment_id", "notice_id", "version", "published_date", "effective_date", "predecessor_id", "changed_conditions", "match_rate", "match_basis", "regional_partner_required", "status", "source_document_id"],
        [
            ["AMD-FO117-01", "FO-2026-117", "1", "2026-09-10", "2026-09-10", "", "Original local match requirement was 20%; no regional letter condition.", "0.20", "total eligible project costs", "false", "Superseded", "DOC-FO117-AMD1"],
            ["AMD-FO117-02", "FO-2026-117", "2", "2026-10-28", "2026-10-28", "AMD-FO117-01", "Raises local match to 25% and adds signed regional-partner commitment-letter requirement.", "0.25", "total eligible project costs", "true", "Current", "DOC-FO117-AMD2"],
            ["AMD-FO204-01", "FO-2026-204", "1", "2026-09-01", "2026-09-01", "", "Requires 10% local match; an approved partner waiver removes the partner condition.", "0.10", "total eligible project costs", "false", "Current", "DOC-FO204-TERMS"],
            ["AMD-FO330-01", "FO-2026-330", "1", "2026-10-01", "2026-10-01", "", "Requires applicant and project to be in the designated rural service area, plus 10% local match.", "0.10", "total eligible project costs", "false", "Current", "DOC-FO330-TERMS"],
        ],
    ),
    "eligibility_criteria": (
        ["criterion_id", "notice_id", "amendment_id", "criterion_type", "rule", "observed_fact", "status", "evidence_document_id"],
        [
            ["FO117-ELIG-APPLICANT", "FO-2026-117", "AMD-FO117-02", "applicant_type", "Applicant must be a local public entity.", "City of Northstar is a local public entity.", "met", "DOC-FO117-ELIG"],
            ["FO117-ELIG-GEOGRAPHY", "FO-2026-117", "AMD-FO117-02", "geography", "Project must serve the Northstar Resilience District.", "The synthetic project geography is the Northstar Resilience District.", "met", "DOC-FO117-ELIG"],
            ["FO117-ELIG-MATCH", "FO-2026-117", "AMD-FO117-02", "match", "25% of total eligible project costs must be documented.", "A portion is confirmed; $450,000 remains proposed and unconfirmed.", "unknown", "DOC-FO117-MATCH"],
            ["FO117-ELIG-PARTNER", "FO-2026-117", "AMD-FO117-02", "partner_letter", "A current signed regional-partner letter must accompany the application.", "No current letter is recorded; 2024 correspondence is historical only.", "unknown", "DOC-FO117-PARTNER"],
            ["FO204-ELIG-APPLICANT", "FO-2026-204", "AMD-FO204-01", "applicant_type", "Applicant must be a local public entity.", "Riverbend City is a local public entity.", "met", "DOC-FO204-TERMS"],
            ["FO204-ELIG-GEOGRAPHY", "FO-2026-204", "AMD-FO204-01", "geography", "Project must be within the eligible Riverbend City area.", "Project geography is Riverbend City.", "met", "DOC-FO204-TERMS"],
            ["FO204-ELIG-MATCH", "FO-2026-204", "AMD-FO204-01", "match", "10% local match must be confirmed.", "A unique $100,000 local allocation is confirmed.", "met", "DOC-FO204-READINESS"],
            ["FO204-ELIG-PARTNER", "FO-2026-204", "AMD-FO204-01", "partner_waiver", "Partner condition may be waived with approved waiver.", "Waiver WAIVER-FO204-01 is approved.", "met", "DOC-FO204-READINESS"],
            ["FO330-ELIG-APPLICANT", "FO-2026-330", "AMD-FO330-01", "applicant_type", "Applicant must be a local public entity.", "City of Northstar is a local public entity.", "met", "DOC-FO330-TERMS"],
            ["FO330-ELIG-GEOGRAPHY", "FO-2026-330", "AMD-FO330-01", "geography", "Project must be in Pine County Rural Service Area.", "Northstar Resilience District is outside Pine County.", "not_met", "DOC-FO330-TERMS"],
            ["FO330-ELIG-MATCH", "FO-2026-330", "AMD-FO330-01", "match", "10% local match must be confirmed.", "A unique $200,000 local allocation is confirmed.", "met", "DOC-FO330-READINESS"],
        ],
    ),
    "budget_lines": (
        ["line_id", "notice_id", "project_id", "category", "amount", "currency", "classification", "evidence_document_id"],
        [
            ["BUD-FO117-01", "FO-2026-117", "PROJECT-RESILIENCE-2026", "Drainage and flood-control assets", "3000000", "USD", "Eligible project cost", "DOC-FO117-NOTICE"],
            ["BUD-FO117-02", "FO-2026-117", "PROJECT-RESILIENCE-2026", "Emergency backup power", "2500000", "USD", "Eligible project cost", "DOC-FO117-NOTICE"],
            ["BUD-FO117-03", "FO-2026-117", "PROJECT-RESILIENCE-2026", "Community cooling and service continuity hubs", "2000000", "USD", "Eligible project cost", "DOC-FO117-NOTICE"],
            ["BUD-FO117-04", "FO-2026-117", "PROJECT-RESILIENCE-2026", "Engineering and resilience planning", "1500000", "USD", "Eligible project cost", "DOC-FO117-NOTICE"],
            ["BUD-FO204-01", "FO-2026-204", "PROJECT-HEAT-READY-2026", "Public facility cooling upgrades", "700000", "USD", "Eligible project cost", "DOC-FO204-TERMS"],
            ["BUD-FO204-02", "FO-2026-204", "PROJECT-HEAT-READY-2026", "Heat safety and access improvements", "300000", "USD", "Eligible project cost", "DOC-FO204-TERMS"],
            ["BUD-FO330-01", "FO-2026-330", "PROJECT-RURAL-ACCESS-2026", "Rural service access improvements", "1500000", "USD", "Eligible project cost", "DOC-FO330-TERMS"],
            ["BUD-FO330-02", "FO-2026-330", "PROJECT-RURAL-ACCESS-2026", "Resilient access infrastructure", "500000", "USD", "Eligible project cost", "DOC-FO330-TERMS"],
        ],
    ),
    "match_sources": (
        ["allocation_id", "notice_id", "project_id", "source", "amount", "currency", "status", "evidence_date", "owner_id", "evidence_document_id", "restrictions"],
        [
            ["ALLOC-CAPITAL-2026-FO117", "FO-2026-117", "PROJECT-RESILIENCE-2026", "2026 capital plan", "1800000", "USD", "Confirmed", "2026-10-31", "FIN-02", "DOC-FO117-MATCH", "Existing capital-plan allocation; count once by allocation ID."],
            ["ALLOC-RESERVE-CANDIDATE-FO117", "FO-2026-117", "PROJECT-RESILIENCE-2026", "Capital reserve", "450000", "USD", "Proposed", "2026-11-09", "FIN-02", "DOC-FO117-FINANCE-MSG", "Do not count until Finance confirms source and restriction eligibility."],
            ["ALLOC-HEAT-LOCAL-FO204", "FO-2026-204", "PROJECT-HEAT-READY-2026", "City resilience fund", "100000", "USD", "Confirmed", "2026-10-20", "FIN-02", "DOC-FO204-READINESS", "Single documented allocation."],
            ["ALLOC-RURAL-LOCAL-FO330", "FO-2026-330", "PROJECT-RURAL-ACCESS-2026", "City infrastructure reserve", "200000", "USD", "Confirmed", "2026-10-18", "FIN-02", "DOC-FO330-READINESS", "Single documented allocation."],
        ],
    ),
    "partners": (
        ["partner_id", "partner_org_id", "notice_id", "name", "region", "partner_type", "qualifies", "commitment_status", "letter_document_id", "letter_date", "historical_proposal_id", "evidence_document_id"],
        [
            ["PARTNER-RTA-FO117", "ORG-RTA", "FO-2026-117", "Regional Transit Authority", "Northstar Resilience District", "Regional public authority", "true", "Missing", "", "", "PR-RESILIENCE-2024", "DOC-FO117-PARTNER"],
            ["PARTNER-RIVERBEND-FO204", "ORG-RIVERBEND-PHD", "FO-2026-204", "Riverbend Public Health District", "Riverbend City", "Public health district", "true", "Not required", "", "", "", "DOC-FO204-READINESS"],
        ],
    ),
    "people": (
        ["person_id", "name", "role", "team", "email"],
        [
            ["PM-01", "Jordan Lee", "Proposal Manager", "Grant Proposal Team", "jordan.lee@example.invalid"],
            ["FIN-02", "Maria Santos", "Finance", "Budget and Finance", "maria.santos@example.invalid"],
            ["EXEC-01", "Dr. Elena Ruiz", "Executive Reviewer", "Program Leadership", "elena.ruiz@example.invalid"],
            ["LEGAL-01", "Sam Patel", "Legal", "Legal and Procurement", "sam.patel@example.invalid"],
        ],
    ),
    "prior_proposals": (
        ["proposal_id", "notice_id", "prior_notice_id", "year", "program_id", "project_id", "partner_id", "outcome", "outcome_evidence", "lesson", "letter_document_id", "evidence_document_id"],
        [
            ["PR-RESILIENCE-2024", "FO-2026-117", "FO-2024-088", "2024", "PROGRAM-RESILIENCE", "PROJECT-RESILIENCE-2024", "PARTNER-RTA-FO117", "Unknown", "No award decision is present in the synthetic evidence.", "The RTA letter shows an established contact path, not current consent or a 2026 commitment.", "DOC-FO117-PRIOR24", "DOC-FO117-PRIOR24"],
        ],
    ),
    "program_performance": (
        ["metric_id", "program_id", "project_id", "measure", "baseline_value", "actual_value", "proposed_target", "period", "unit", "source_document_id"],
        [
            ["PERF-RES-01", "PROGRAM-RESILIENCE", "PROJECT-RESILIENCE-2026", "Critical facilities with backup power", "35", "", "70", "2026 baseline / proposed project target", "percent", "DOC-FO117-PERFORMANCE"],
            ["PERF-RES-02", "PROGRAM-RESILIENCE", "PROJECT-RESILIENCE-2026", "Prior city resilience projects delivered on schedule", "8", "8", "", "2025-2026", "projects out of 10", "DOC-FO117-PERFORMANCE"],
            ["PERF-HEAT-01", "PROGRAM-HEAT-READY", "PROJECT-HEAT-READY-2026", "Public facilities with cooling access", "4", "", "8", "2026 baseline / proposed project target", "facilities", "DOC-FO204-TERMS"],
            ["PERF-RURAL-01", "PROGRAM-RURAL-ACCESS", "PROJECT-RURAL-ACCESS-2026", "Rural service routes served", "0", "", "3", "2026 proposed project target", "routes", "DOC-FO330-TERMS"],
        ],
    ),
    "community_metrics": (
        ["metric_id", "program_id", "geography_id", "metric", "value", "unit", "period", "eligibility_relevance", "source_document_id"],
        [
            ["COMM-RES-01", "PROGRAM-RESILIENCE", "GEO-NORTHSTAR-DISTRICT", "Residents in priority service area", "18400", "people", "2026-10-31", "Population served by resilience assets.", "DOC-FO117-COMMUNITY"],
            ["COMM-RES-02", "PROGRAM-RESILIENCE", "GEO-NORTHSTAR-DISTRICT", "Residents in households below local median income", "32", "percent", "2026-10-31", "Notice scoring gives weight to service continuity for underserved communities.", "DOC-FO117-COMMUNITY"],
            ["COMM-HEAT-01", "PROGRAM-HEAT-READY", "GEO-RIVERBEND-CITY", "Residents in high heat-risk census tracts", "6200", "people", "2026-09-30", "Program objective prioritizes public heat-safety access.", "DOC-FO204-TERMS"],
        ],
    ),
    "staff_workload": (
        ["workload_id", "person_id", "notice_id", "team", "period", "available_capacity_hours", "committed_work_hours", "unavailable_from", "unavailable_through", "work_must_finish_by", "dependency_ids", "evidence_document_id"],
        [
            ["WORKLOAD-LEGAL-FO117", "LEGAL-01", "FO-2026-117", "Legal and Procurement", "2026-11", "8", "6", "2026-11-23", "2026-11-27", "2026-11-20", "TASK-117-MATCH;TASK-117-PARTNER", "DOC-FO117-LEGAL-AVAIL"],
            ["WORKLOAD-PM-FO117", "PM-01", "FO-2026-117", "Grant Proposal Team", "2026-11", "24", "18", "", "", "2026-12-16", "TASK-117-MATCH;TASK-117-PARTNER", "DOC-FO117-HUDDLE"],
        ],
    ),
    "scheduling_slots": (
        ["slot_id", "notice_id", "reviewer_id", "review_id", "start_date", "start_time", "end_date", "end_time", "timezone", "status", "purpose", "dependency_ids", "evidence_document_id"],
        [
            ["SLOT-EXEC-FO117-20261119", "FO-2026-117", "EXEC-01", "REVIEW-FO-2026-117-2026-11-05", "2026-11-19", "10:00", "2026-11-19", "11:00", "America/New_York", "Available", "Review documented match and remaining risks; not a final unconditional approval.", "TASK-117-MATCH", "DOC-FO117-HUDDLE"],
        ],
    ),
    "approvals": (
        ["approval_id", "notice_id", "project_id", "approval_type", "required_owner_id", "state", "decision", "decision_date", "conditions", "dependencies", "evidence_document_id", "record_type"],
        [
            ["REVIEW-FO-2026-117-2026-11-05", "FO-2026-117", "PROJECT-RESILIENCE-2026", "Go/no-go pursuit review", "EXEC-01", "Pending", "Pursue - pending", "2026-11-05", "Confirm match and current partner letter; executive review may be conditional if evidence remains open.", "TASK-117-MATCH;SLOT-EXEC-FO117-20261119;TASK-117-PARTNER", "DOC-FO117-REVIEW", "Recorded review; not funding approval"],
            ["APPROVAL-FO204-READINESS", "FO-2026-204", "PROJECT-HEAT-READY-2026", "Internal submission readiness", "EXEC-01", "Approved", "Ready to submit", "2026-11-10", "Application still requires submission by its deadline.", "MATCH-HEAT-READY;PARTNER-WAIVER-FO204", "DOC-FO204-READINESS", "Internal readiness only; not a funding award"],
        ],
    ),
    "submissions": (
        ["submission_id", "notice_id", "project_id", "proposal_owner_id", "pursuit_state", "submission_state", "deadline", "required_artifacts", "blockers", "unknown_requirements", "dependency_ids", "submitted_at", "evidence_document_id"],
        [
            ["SUBMISSION-FO117", "FO-2026-117", "PROJECT-RESILIENCE-2026", "PM-01", "Pursue - pending", "Not submitted", "2026-12-16", "Match confirmation; current partner letter; legal/procurement review; authorized final approval; application package", "450000 match gap; current partner letter missing; legal review due before leave", "Portal-specific certifications/attachments not verified in synthetic corpus.", "TASK-117-MATCH;TASK-117-PARTNER;WORKLOAD-LEGAL-FO117;REVIEW-FO-2026-117-2026-11-05", "", "DOC-FO117-TRACKER2"],
            ["SUBMISSION-FO204", "FO-2026-204", "PROJECT-HEAT-READY-2026", "PM-01", "Pursue - approved to submit", "Not submitted", "2026-12-10", "Application package", "None recorded in synthetic readiness review", "Portal-specific attachments not verified.", "APPROVAL-FO204-READINESS", "", "DOC-FO204-READINESS"],
            ["SUBMISSION-FO330", "FO-2026-330", "PROJECT-RURAL-ACCESS-2026", "PM-01", "Do not pursue - eligibility failed", "Not submitted", "2027-01-15", "Eligible rural geography; application package", "Applicant geography is outside eligible area.", "Other requirements are not evaluated after geography failure.", "", "", "DOC-FO330-READINESS"],
        ],
    ),
    "proposal_tasks": (
        ["task_id", "notice_id", "description", "owner_id", "status", "due_date", "dependency_ids", "supporting_document_ids"],
        [
            ["TASK-117-MATCH", "FO-2026-117", "Confirm and document the proposed capital-reserve match without changing the existing capital-plan allocation.", "FIN-02", "Open", "2026-11-18", "", "DOC-FO117-FINANCE-MSG;DOC-FO117-TRACKER2"],
            ["TASK-117-PARTNER", "FO-2026-117", "Obtain the current Regional Transit Authority commitment letter after executive review.", "PM-01", "Open", "2026-11-20", "SLOT-EXEC-FO117-20261119", "DOC-FO117-PARTNER-MSG;DOC-FO117-HUDDLE"],
        ],
    ),
    "source_documents": (
        ["document_id", "notice_id", "title", "source", "source_type", "filename", "version", "publication_date", "effective_from", "supersedes", "summary"],
        [
            ["DOC-FO117-NOTICE", "FO-2026-117", "Original opportunity notice", "foundry", "Funding notice", "FO-2026-117_notice_v1.md", "1", "2026-09-01", "2026-09-01", "", "Applicant, geographic and project purpose terms."],
            ["DOC-FO117-AMD1", "FO-2026-117", "Amendment 1", "foundry", "Superseded amendment", "FO-2026-117_amendment_1_v1.md", "1", "2026-09-10", "2026-09-10", "", "Earlier 20% match and no partner-letter condition."],
            ["DOC-FO117-AMD2", "FO-2026-117", "Amendment 2", "foundry", "Current effective amendment", "FO-2026-117_amendment_2_v1.md", "2", "2026-10-28", "2026-10-28", "DOC-FO117-AMD1", "Current 25% match and signed regional partner letter."],
            ["DOC-FO117-ELIG", "FO-2026-117", "Applicant eligibility rules", "foundry", "Eligibility guidance", "FO-2026-117_applicant_eligibility_v1.md", "1", "2026-09-01", "2026-09-01", "", "Local public applicant and eligible geography."],
            ["DOC-FO117-MATCH", "FO-2026-117", "Local matching-fund policy", "foundry", "Finance policy", "FO-2026-117_match_policy_v1.md", "1", "2026-10-30", "2026-10-30", "", "Confirmed funds counted once by allocation ID; proposed sources excluded."],
            ["DOC-FO117-PARTNER", "FO-2026-117", "Regional partner guidance", "foundry", "Partner guidance", "FO-2026-117_regional_partner_guidance_v1.md", "1", "2026-10-28", "2026-10-28", "", "Current signed letter must accompany application."],
            ["DOC-FO117-LEGAL", "FO-2026-117", "Legal and procurement checklist", "foundry", "Legal checklist", "FO-2026-117_legal_procurement_checklist_v1.md", "1", "2026-10-30", "2026-10-30", "", "Review must precede authorized submission."],
            ["DOC-FO117-APPROVAL", "FO-2026-117", "Institutional approval policy", "foundry", "Approval policy", "FO-2026-117_approval_policy_v1.md", "1", "2026-10-15", "2026-10-15", "", "Pursuit status and approval are distinct from a funding award."],
            ["DOC-FO117-COMMUNITY", "FO-2026-117", "Community needs snapshot", "foundry", "Community evidence", "FO-2026-117_community_needs_v1.md", "1", "2026-10-31", "2026-10-31", "", "Synthetic population and underserved-community indicators."],
            ["DOC-FO117-PERFORMANCE", "FO-2026-117", "Program outcomes and proposed targets", "foundry", "Program performance", "FO-2026-117_program_outcomes_v1.md", "1", "2026-10-31", "2026-10-31", "", "Prior delivery and proposed, not achieved, project targets."],
            ["DOC-FO117-PRIOR24", "FO-2026-117", "2024 prior proposal record", "work", "Prior proposal", "FO-2026-117_prior_proposal_2024_v1.md", "1", "2024-08-01", "2024-08-01", "", "Historical RTA letter lead; award outcome unknown."],
            ["DOC-FO117-TRACKER1", "FO-2026-117", "Readiness tracker v1", "work", "Superseded tracker", "FO-2026-117_readiness_tracker_v1.md", "1", "2026-11-06", "2026-11-06", "", "Stale 20% match assumption, superseded by v2."],
            ["DOC-FO117-TRACKER2", "FO-2026-117", "Readiness tracker v2", "work", "Current readiness tracker", "FO-2026-117_readiness_tracker_v2.md", "2", "2026-11-09", "2026-11-09", "DOC-FO117-TRACKER1", "Current 25% match gap, tasks and unresolved partner letter."],
            ["DOC-FO117-MATCH-MEMO1", "FO-2026-117", "Match-funding memo v1", "work", "Superseded match memo", "FO-2026-117_match_funding_memo_v1.md", "1", "2026-11-06", "2026-11-06", "", "Earlier match assumption, superseded after Amendment 2."],
            ["DOC-FO117-MATCH-MEMO2", "FO-2026-117", "Match-funding memo v2", "work", "Current match memo", "FO-2026-117_match_funding_memo_v2.md", "2", "2026-11-09", "2026-11-09", "DOC-FO117-MATCH-MEMO1", "Separates confirmed capital-plan allocation from proposed reserve."],
            ["DOC-FO117-DECISION1", "FO-2026-117", "Pursue decision brief v1", "work", "Superseded decision brief", "FO-2026-117_pursue_decision_brief_v1.md", "1", "2026-11-06", "2026-11-06", "", "Stale assumptions superseded by v2."],
            ["DOC-FO117-DECISION2", "FO-2026-117", "Pursue decision brief v2", "work", "Current decision brief", "FO-2026-117_pursue_decision_brief_v2.md", "2", "2026-11-09", "2026-11-09", "DOC-FO117-DECISION1", "Conditional pursuit and decision boundaries."],
            ["DOC-FO117-REVIEW", "FO-2026-117", "Go/no-go review minutes", "work", "Human review", "FO-2026-117_review_minutes_2026-11-05.md", "1", "2026-11-05", "2026-11-05", "", "Recorded Pursue - pending disposition."],
            ["DOC-FO117-HUDDLE", "FO-2026-117", "Proposal huddle notes", "work", "Proposal workflow", "FO-2026-117_proposal_huddle_2026-11-09.md", "1", "2026-11-09", "2026-11-09", "", "Owner tasks, review slot, sequencing and leave constraints."],
            ["DOC-FO117-FINANCE-MSG", "FO-2026-117", "Finance match confirmation message", "work", "Synthetic Teams message", "proposal_teams_messages.json", "1", "2026-11-09", "2026-11-09", "", "Capital reserve remains proposed; Maria owns confirmation."],
            ["DOC-FO117-PARTNER-MSG", "FO-2026-117", "Partner outreach context", "work", "Synthetic email context", "proposal_email_context.json", "1", "2026-11-09", "2026-11-09", "", "Current partner letter is not yet received."],
            ["DOC-FO117-LEGAL-AVAIL", "FO-2026-117", "Legal reviewer availability", "work", "Staff calendar evidence", "FO-2026-117_legal_availability_v1.md", "1", "2026-11-09", "2026-11-09", "", "Sam unavailable Nov 23-27; finish review by Nov 20."],
            ["DOC-FO117-EXTERNAL", "FO-2026-117", "Agency guidance snapshot", "web", "Synthetic cached guidance", "FO-2026-117_agency_guidance_v1.md", "1", "2026-11-02", "2026-11-02", "", "Locally cached synthetic guidance, not live web evidence."],
            ["DOC-FO204-TERMS", "FO-2026-204", "Heat-ready notice and scoring terms", "foundry", "Funding notice", "FO-2026-204_terms_v1.md", "1", "2026-09-01", "2026-09-01", "", "Eligible project and scoring objectives."],
            ["DOC-FO204-READINESS", "FO-2026-204", "Heat-ready readiness review", "work", "Readiness record", "FO-2026-204_readiness_v1.md", "1", "2026-11-10", "2026-11-10", "", "Confirmed match, partner waiver and internal readiness approval."],
            ["DOC-FO330-TERMS", "FO-2026-330", "Rural access notice terms", "foundry", "Funding notice", "FO-2026-330_terms_v1.md", "1", "2026-10-01", "2026-10-01", "", "Geographic restriction and required 10% match."],
            ["DOC-FO330-READINESS", "FO-2026-330", "Rural access eligibility review", "work", "Readiness record", "FO-2026-330_readiness_v1.md", "1", "2026-11-12", "2026-11-12", "", "Failed geography condition; other eligibility not inferred."],
            ["DOC-FO117-STRUCTURED", "FO-2026-117", "Structured funding snapshot", "fabric", "Structured operations snapshot", "FO-2026-117_structured_snapshot_v1.md", "1", "2026-11-16", "2026-11-16", "", "Synthetic structured records and fixture-design financing basis."],
            ["DOC-FO204-STRUCTURED", "FO-2026-204", "Heat-ready structured funding snapshot", "fabric", "Structured operations snapshot", "FO-2026-204_structured_snapshot_v1.md", "1", "2026-11-16", "2026-11-16", "", "Synthetic linked opportunity, budget, match, and readiness records."],
            ["DOC-FO330-STRUCTURED", "FO-2026-330", "Rural access structured funding snapshot", "fabric", "Structured operations snapshot", "FO-2026-330_structured_snapshot_v1.md", "1", "2026-11-16", "2026-11-16", "", "Synthetic linked opportunity, geography, budget, and match records."],
        ],
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
