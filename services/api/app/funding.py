from __future__ import annotations

import csv
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel

from app.config import Settings
from app.schemas import Evidence, Source
from app.sources.base import evidence_doc_url


CriterionStatus = Literal["met", "not_met", "unknown"]


class FundingPerson(BaseModel):
    id: str
    display: str
    role: str


class FundingOpportunity(BaseModel):
    id: str
    programId: str
    projectId: str
    title: str
    agency: str
    deadline: str
    deadlineTimezone: str
    asOfDate: str
    eligibleCostBasis: int
    requestedAmount: int
    projectCostBasis: str


class FundingCriterion(BaseModel):
    id: str
    text: str
    status: CriterionStatus
    evidenceRefs: list[str]


class FundingTask(BaseModel):
    id: str
    text: str
    owner: FundingPerson
    due: str
    recordedState: str
    dependencyIds: list[str]
    evidenceRefs: list[str]
    status: str = "Drafted (not submitted)"


class FundingRationale(BaseModel):
    heading: str
    text: str
    evidenceRefs: list[str]


class CriticalPathStep(BaseModel):
    id: str
    order: int
    title: str
    owner: FundingPerson | None = None
    due: str | None = None
    status: str
    dependency: str
    detail: str
    evidenceRefs: list[str]


class FundingAssessment(BaseModel):
    question: str
    answer: str
    bottomLine: str
    opportunity: FundingOpportunity
    pursuitStatus: str
    recommendation: str
    eligibility: str
    amendmentSummary: str
    matchBasis: str
    matchRequired: int
    matchConfirmed: int
    matchProposed: int
    matchGap: int
    deadlineDays: int
    criteria: list[FundingCriterion]
    rationale: list[FundingRationale]
    partner: str
    partnerEvidence: str
    tasks: list[FundingTask]
    criticalPath: list[CriticalPathStep]
    executiveReview: str
    legalConstraint: str
    submissionStatus: str
    unknownRequirements: str
    evidence: list[Evidence]
    answerRefs: list[str]
    sourceMap: list[dict[str, object]]
    trace: list[dict[str, object]]
    mode: Literal["mock", "live"] = "mock"
    disclaimer: str = (
        "Synthetic grant decision support. Human review required. No funds approved, tasks "
        "submitted, meetings booked, or applications submitted."
    )


def _read_rows(data_dir: Path, table: str) -> list[dict[str, str]]:
    with (data_dir / "fabric" / "funding_ops" / f"{table}.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        return list(csv.DictReader(handle))


def _money(value: str | Decimal) -> int:
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _person(person_id: str, people: dict[str, dict[str, str]]) -> FundingPerson:
    record = people[person_id]
    return FundingPerson(id=person_id, display=record["name"], role=record["role"])


def _select_opportunity(question: str, opportunities: list[dict[str, str]]) -> dict[str, str]:
    normalized = question.casefold()
    scored: list[tuple[int, dict[str, str]]] = []
    for row in opportunities:
        score = 0
        terms = [row["notice_id"], row["title"], *row["query_terms"].split(";")]
        for term in terms:
            term = term.strip().casefold()
            if term and term in normalized:
                score = max(score, 10 + len(term))
        scored.append((score, row))
    best_score, selected = max(
        scored, key=lambda candidate: (candidate[0], candidate[1]["notice_id"])
    )
    if best_score:
        return selected
    return next((row for row in opportunities if row["notice_id"] == "FO-2026-117"), selected)


def _doc_url(source: str, filename: str) -> str:
    subdir = {
        Source.FOUNDRY.value: "foundry_docs",
        Source.FABRIC.value: "funding_ops",
        Source.WORK.value: "work",
        Source.WEB.value: "web",
    }[source]
    return evidence_doc_url(subdir, filename)


def _citation(
    data_dir: Path, document: dict[str, str]
) -> Evidence:
    source = Source(document["source"])
    directory = {
        Source.FOUNDRY: "foundry_docs",
        Source.FABRIC: "fabric/funding_ops",
        Source.WORK: "work",
        Source.WEB: "web",
    }[source]
    path = data_dir / directory / document["filename"]
    text = path.read_text(encoding="utf-8")
    snippet = " ".join(text.split())[:300]
    provenance = (
        f"{document['source_type']} · v{document['version']} · "
        f"published {document['publication_date']}"
    )
    if document["effective_from"]:
        provenance += f" · effective {document['effective_from']}"
    return Evidence(
        refId=document["document_id"],
        source=source,
        title=document["title"],
        snippet=snippet,
        url=_doc_url(document["source"], document["filename"]),
        sourceType=provenance,
    )


def _criterion_status(
    row: dict[str, str],
    opportunity: dict[str, str],
    amendment: dict[str, str],
    confirmed_match: int,
    required_match: int,
    partner: dict[str, str] | None,
    as_of: date,
) -> CriterionStatus:
    kind = row["criterion_type"]
    if kind == "applicant_type":
        allowed = {item.strip() for item in opportunity["eligible_applicant_types"].split("|")}
        return "met" if opportunity["applicant_type"] in allowed else "not_met"
    if kind == "geography":
        allowed = {item.strip() for item in opportunity["eligible_geographies"].split("|")}
        return "met" if opportunity["applicant_geography"] in allowed else "not_met"
    if kind == "match":
        return "met" if confirmed_match >= required_match else "unknown"
    if kind == "partner_letter":
        if amendment["regional_partner_required"].casefold() != "true":
            return "met"
        if partner is None:
            return "unknown"
        if (
            partner["commitment_status"] == "Received"
            and partner["letter_document_id"]
            and partner["letter_date"]
            and date.fromisoformat(partner["letter_date"]) <= as_of
        ):
            return "met"
        return "not_met" if partner["commitment_status"] == "Declined" else "unknown"
    return row["status"] if row["status"] in {"met", "not_met", "unknown"} else "unknown"  # type: ignore[return-value]


def assess_funding(
    settings: Settings,
    question: str,
    *,
    source_states: dict[Source, str] | None = None,
) -> FundingAssessment:
    """Build a deterministic, data-linked funding assessment from synthetic source records."""
    data_dir = settings.DATA_DIR
    with (data_dir / "registry" / "funding_registry.yaml").open(encoding="utf-8") as handle:
        registry = yaml.safe_load(handle)
    all_rows = {
        name: _read_rows(data_dir, name)
        for name in (
            "funding_opportunities",
            "amendments",
            "eligibility_criteria",
            "budget_lines",
            "match_sources",
            "partners",
            "people",
            "prior_proposals",
            "program_performance",
            "community_metrics",
            "staff_workload",
            "scheduling_slots",
            "approvals",
            "submissions",
            "proposal_tasks",
            "source_documents",
        )
    }
    opportunities = all_rows["funding_opportunities"]
    scenario_date = date.fromisoformat(registry["meta"]["scenario_as_of"])
    query = question.strip()
    opportunity = _select_opportunity(query, opportunities)
    notice_id = opportunity["notice_id"]
    if opportunity["as_of_date"] != scenario_date.isoformat():
        raise ValueError(f"{notice_id} and registry disagree on the pinned scenario date.")

    amendments = [
        row for row in all_rows["amendments"]
        if row["notice_id"] == notice_id
        and date.fromisoformat(row["effective_date"]) <= scenario_date
    ]
    if not amendments:
        raise ValueError(f"{notice_id} has no effective amendment on the scenario date.")
    amendment = max(amendments, key=lambda row: (row["effective_date"], int(row["version"])))

    budget_rows = [
        row for row in all_rows["budget_lines"]
        if row["notice_id"] == notice_id and row["classification"] == "Eligible project cost"
    ]
    eligible_cost = sum(int(row["amount"]) for row in budget_rows)
    if eligible_cost != int(opportunity["total_eligible_cost"]):
        raise ValueError(f"{notice_id} budget lines do not reconcile to eligible project costs.")
    required_match = _money(
        Decimal(eligible_cost) * Decimal(amendment["match_rate"])
    )
    allocations: dict[str, dict[str, str]] = {}
    for row in all_rows["match_sources"]:
        if row["notice_id"] != notice_id:
            continue
        existing = allocations.get(row["allocation_id"])
        if existing and existing != row:
            raise ValueError(f"Conflicting duplicate match allocation {row['allocation_id']}.")
        allocations[row["allocation_id"]] = row
    match_rows = list(allocations.values())
    confirmed_match = sum(
        int(row["amount"]) for row in match_rows if row["status"].casefold() == "confirmed"
    )
    proposed_match = sum(
        int(row["amount"]) for row in match_rows if row["status"].casefold() == "proposed"
    )
    match_gap = max(required_match - confirmed_match, 0)
    requested_amount = max(eligible_cost - required_match, 0)

    partners = [row for row in all_rows["partners"] if row["notice_id"] == notice_id]
    partner = partners[0] if partners else None
    criteria_rows = [
        row for row in all_rows["eligibility_criteria"] if row["notice_id"] == notice_id
    ]
    if not criteria_rows:
        criteria_rows = [{
            "criterion_id": f"{notice_id}-ELIGIBILITY-UNKNOWN",
            "criterion_type": "unknown",
            "rule": "Applicable eligibility evidence has not been modeled.",
            "observed_fact": "",
            "status": "unknown",
            "evidence_document_id": "",
        }]
    people = {row["person_id"]: row for row in all_rows["people"]}
    documents = {row["document_id"]: row for row in all_rows["source_documents"]}
    selected_docs: set[str] = {amendment["source_document_id"]}
    selected_docs.update(row["evidence_document_id"] for row in criteria_rows if row["evidence_document_id"])
    selected_docs.update(row["evidence_document_id"] for row in match_rows if row["evidence_document_id"])
    selected_docs.update(row["evidence_document_id"] for row in partners if row["evidence_document_id"])
    selected_docs.update(
        row["letter_document_id"] for row in partners if row["letter_document_id"]
    )
    selected_docs.update(
        row["source_document_id"] for row in all_rows["program_performance"]
        if row["program_id"] == opportunity["program_id"]
    )
    selected_docs.update(
        row["source_document_id"] for row in all_rows["community_metrics"]
        if row["program_id"] == opportunity["program_id"]
    )
    selected_docs.update(
        row["evidence_document_id"] for row in all_rows["prior_proposals"]
        if row["notice_id"] == notice_id and row["evidence_document_id"]
    )
    task_rows = [row for row in all_rows["proposal_tasks"] if row["notice_id"] == notice_id]
    selected_docs.update(
        document_id
        for row in task_rows
        for document_id in row["supporting_document_ids"].split(";")
        if document_id
    )
    approvals = [
        row for row in all_rows["approvals"]
        if row["notice_id"] == notice_id
        and date.fromisoformat(row["decision_date"]) <= scenario_date
    ]
    approvals.sort(key=lambda row: row["decision_date"])
    approval = approvals[-1] if approvals else None
    if approval and approval["evidence_document_id"]:
        selected_docs.add(approval["evidence_document_id"])
    workload_rows = [
        row for row in all_rows["staff_workload"] if row["notice_id"] == notice_id
    ]
    selected_docs.update(row["evidence_document_id"] for row in workload_rows if row["evidence_document_id"])
    slots = [row for row in all_rows["scheduling_slots"] if row["notice_id"] == notice_id]
    slots.sort(key=lambda row: (row["start_date"], row["start_time"]))
    selected_docs.update(row["evidence_document_id"] for row in slots if row["evidence_document_id"])
    submissions = [
        row for row in all_rows["submissions"] if row["notice_id"] == notice_id
    ]
    submission = submissions[0] if submissions else None
    if submission and submission["evidence_document_id"]:
        selected_docs.add(submission["evidence_document_id"])
    # Keep version conflicts and the authority rules inspectable in the returned evidence packet.
    selected_docs.update(
        row["document_id"] for row in documents.values() if row["notice_id"] == notice_id
    )
    superseded_document_ids = {
        row["supersedes"] for row in documents.values()
        if row["supersedes"] and row["effective_from"]
        and date.fromisoformat(row["effective_from"]) <= scenario_date
    }
    active_document_ids = {
        row["document_id"] for row in documents.values()
        if row["notice_id"] == notice_id
        and (not row["effective_from"] or date.fromisoformat(row["effective_from"]) <= scenario_date)
        and row["document_id"] not in superseded_document_ids
    }
    selected_docs.intersection_update(active_document_ids)

    evidence = [
        _citation(data_dir, documents[document_id])
        for document_id in sorted(selected_docs)
        if document_id in documents
    ]
    evidence_by_id = {item.refId: item for item in evidence}
    criteria: list[FundingCriterion] = []
    for row in criteria_rows:
        status = _criterion_status(
            row, opportunity, amendment, confirmed_match, required_match, partner, scenario_date
        )
        if row["criterion_type"] == "match":
            criterion_text = (
                f"{Decimal(amendment['match_rate'])*100:.0f}% local match: "
                f"${required_match:,} required; ${confirmed_match:,} confirmed; "
                f"${match_gap:,} gap."
            )
        elif row["criterion_type"] == "partner_letter":
            state = partner["commitment_status"].casefold() if partner else "unknown"
            criterion_text = (
                "A current signed partner letter from the regional partner is required; "
                f"recorded state: {state}."
            )
        else:
            criterion_text = f"{row['rule']} {row['observed_fact']}".strip()
        criterion_refs = [row["evidence_document_id"]] if row["evidence_document_id"] else []
        if (
            row["criterion_type"] == "partner_letter" and partner
            and partner["letter_document_id"]
        ):
            criterion_refs.append(partner["letter_document_id"])
        criteria.append(FundingCriterion(
            id=row["criterion_id"],
            text=criterion_text,
            status=status,
            evidenceRefs=sorted(set(criterion_refs)),
        ))

    tasks: list[FundingTask] = []
    for row in task_rows:
        task_evidence = [
            item for item in row["supporting_document_ids"].split(";") if item in evidence_by_id
        ]
        task_text = row["description"]
        if row["task_id"] == "TASK-117-MATCH" and match_gap:
            task_text = f"Confirm and document the proposed capital-reserve source for the ${match_gap:,} remaining gap."
        dependencies = [item for item in row["dependency_ids"].split(";") if item]
        tasks.append(FundingTask(
            id=row["task_id"],
            text=task_text,
            owner=_person(row["owner_id"], people),
            due=row["due_date"],
            recordedState=row["status"],
            dependencyIds=dependencies,
            evidenceRefs=task_evidence,
        ))
    tasks.sort(key=lambda item: (item.due, item.id))

    program_metrics = [
        row for row in all_rows["program_performance"]
        if row["program_id"] == opportunity["program_id"]
    ]
    community_metrics = [
        row for row in all_rows["community_metrics"]
        if row["program_id"] == opportunity["program_id"]
    ]
    prior = next(
        (row for row in all_rows["prior_proposals"] if row["notice_id"] == notice_id),
        None,
    )
    match_refs = sorted({
        amendment["source_document_id"],
        *(row["evidence_document_id"] for row in match_rows if row["evidence_document_id"]),
    })
    applicant_refs = sorted({
        row["evidence_document_id"] for row in criteria_rows
        if row["criterion_type"] in {"applicant_type", "geography"} and row["evidence_document_id"]
    })
    partner_refs = sorted({
        row["evidence_document_id"] for row in partners if row["evidence_document_id"]
    } | {amendment["source_document_id"]})
    program_refs = sorted({
        row["source_document_id"] for row in program_metrics if row["source_document_id"]
    } | {
        row["source_document_id"] for row in community_metrics if row["source_document_id"]
    })
    if prior and prior["evidence_document_id"]:
        program_refs.append(prior["evidence_document_id"])

    match_readiness = (
        f"${match_gap:,} remains unconfirmed" if match_gap else "is fully confirmed"
    )
    rationale = [
        FundingRationale(
            heading="Eligibility and readiness",
            text=(
                f"The applicant type and project geography are checked against the notice. "
                f"Amendment {amendment['version']} "
                f"{Decimal(amendment['match_rate'])*100:.0f}% match requirement {match_readiness}. "
                + (
                    "No current regional-partner letter is required."
                    if amendment["regional_partner_required"].casefold() != "true"
                    else (
                        f"The current regional-partner letter is "
                        f"{partner['commitment_status'].casefold() if partner else 'not documented'}."
                    )
                )
            ),
            evidenceRefs=sorted(set(applicant_refs + match_refs + partner_refs)),
        ),
    ]
    if program_metrics or community_metrics:
        performance_text = "; ".join(
            (
                f"{row['measure']}: baseline {row['baseline_value']}"
                + (f", actual {row['actual_value']}" if row["actual_value"] else "")
                + (f", proposed target {row['proposed_target']}" if row["proposed_target"] else "")
                + f" {row['unit']}"
            )
            for row in program_metrics
        )
        community_text = "; ".join(
            f"{int(row['value']):,} {row['unit']} — {row['metric']} ({row['eligibility_relevance']})"
            for row in community_metrics
        )
        prior_text = (
            f" Prior proposal outcome is {prior['outcome'].casefold()}; {prior['lesson']}"
            if prior else ""
        )
        context_limits = []
        if any(row["proposed_target"] for row in program_metrics):
            context_limits.append("Proposed targets are not achieved results.")
        if prior:
            context_limits.append(
                "Prior partner experience does not establish current consent or award likelihood."
            )
        rationale.append(FundingRationale(
            heading=(
                "Why conditional pursuit may be worthwhile"
                if notice_id == "FO-2026-117" else "Program and community context"
            ),
            text=(
                f"The proposed work aligns with {opportunity['program_purpose']} "
                f"Community evidence: {community_text or 'not recorded'}. "
                f"Program evidence: {performance_text or 'not recorded'}.{prior_text} "
                f"{' '.join(context_limits)}"
            ),
            evidenceRefs=sorted(set(program_refs)),
        ))

    deadline = date.fromisoformat(opportunity["deadline"])
    deadline_days = (deadline - scenario_date).days
    status = approval["decision"] if approval else (
        submission["pursuit_state"] if submission else "Pending review"
    )
    statuses = {criterion.status for criterion in criteria}
    unknown_criteria = [item for item in criteria if item.status == "unknown"]
    if "not_met" in statuses:
        eligibility = "Not eligible on at least one evidenced criterion"
        recommendation = (
            "Do not pursue unless an authorized reviewer resolves the failed criterion; "
            f"{len(unknown_criteria)} other criterion/criteria remain unknown."
            if unknown_criteria
            else "Do not pursue on the evidenced failed criterion unless an authorized reviewer resolves it."
        )
    elif "unknown" in statuses:
        eligibility = "Applicant criteria evidenced; application readiness remains conditional"
        recommendation = "Continue conditionally; revisit only after match, partner, and required reviews are documented."
    else:
        eligibility = "Modeled eligibility criteria met; confirm any remaining notice requirements"
        recommendation = "Ready for human submission review; this assessment does not approve funding or submit an application."

    partner_required = amendment["regional_partner_required"].casefold() == "true"
    if not partner_required:
        partner_evidence = (
            f"{partner['name']} is listed as a potential partner, but this notice does not require "
            "a regional-partner commitment letter."
            if partner else "This notice does not require a regional-partner commitment letter."
        )
    elif partner:
        letter_received_as_of = (
            partner["commitment_status"] == "Received"
            and partner["letter_document_id"]
            and partner["letter_date"]
            and date.fromisoformat(partner["letter_date"]) <= scenario_date
        )
        partner_state = (
            "received"
            if letter_received_as_of
            else "not yet evidenced as of the scenario date"
            if partner["commitment_status"] == "Received"
            else partner["commitment_status"].casefold()
        )
        partner_evidence = (
            f"{partner['name']} is a qualifying lead; current letter status is "
            f"{partner_state}."
        )
        if partner["historical_proposal_id"]:
            partner_evidence += " Historical participation is not a current commitment."
    else:
        partner_evidence = (
            "No partner record is present; this is unknown, not evidence that a required partner "
            "is unavailable."
        )

    match_basis = amendment["match_basis"]
    basis_detail = opportunity["project_cost_basis"]
    timezone = ZoneInfo(opportunity["deadline_timezone"])
    executive_review = "No review slot is recorded."
    executive_refs: list[str] = []
    critical_path: list[CriticalPathStep] = []
    step_order = 1
    if tasks:
        for task in tasks:
            critical_path.append(CriticalPathStep(
                id=task.id,
                order=step_order,
                title=f"{task.id}: {task.text}",
                owner=task.owner,
                due=task.due,
                status=task.recordedState,
                dependency="; ".join(task.dependencyIds) or "None recorded",
                detail=(
                    "This is an open workflow item. The UI presents a draft only; it is not "
                    "created or submitted in an external task system."
                ),
                evidenceRefs=task.evidenceRefs,
            ))
            step_order += 1

    if slots:
        slot = slots[0]
        slot_person = _person(slot["reviewer_id"], people)
        slot_date = date.fromisoformat(slot["start_date"])
        offset = datetime.combine(
            slot_date, datetime.strptime(slot["start_time"], "%H:%M").time(), tzinfo=timezone
        ).strftime("%Z, UTC%z")
        offset = f"{offset[:-2]}:{offset[-2:]}"
        executive_review = (
            f"{slot['start_date']}, {slot['start_time']}-{slot['end_time']} "
            f"{slot['timezone']} ({offset}) with {slot_person.display} "
            f"(available review slot; not booked)"
        )
        executive_refs = [slot["evidence_document_id"]] if slot["evidence_document_id"] else []
        critical_path.append(CriticalPathStep(
            id=slot["slot_id"],
            order=step_order,
            title="Bring documented match and remaining risks to executive review",
            owner=slot_person,
            due=slot["start_date"],
            status=slot["status"],
            dependency=slot["dependency_ids"].replace(";", "; ") or "None recorded",
            detail=slot["purpose"] + " Availability is not a booking or unconditional approval.",
            evidenceRefs=executive_refs,
        ))
        step_order += 1
    critical_path.sort(key=lambda item: (item.due or "9999-12-31", item.order))
    # Keep the requested review before the dependent partner task when their calendar dates tie.
    critical_path.sort(key=lambda item: (
        item.due or "9999-12-31",
        0 if item.id.startswith("SLOT-") else 1 if item.id == "TASK-117-MATCH" else 2,
        item.id,
    ))
    for index, step in enumerate(critical_path, start=1):
        step.order = index

    legal_lines = [row for row in workload_rows if row["unavailable_from"]]
    legal_constraint = "No legal availability constraint is recorded."
    legal_refs: list[str] = []
    if legal_lines:
        legal = legal_lines[0]
        legal_owner = _person(legal["person_id"], people)
        legal_constraint = (
            f"{legal_owner.display} is unavailable {legal['unavailable_from']} through "
            f"{legal['unavailable_through']}; legal/procurement review must finish by "
            f"{legal['work_must_finish_by']}."
        )
        legal_refs = [legal["evidence_document_id"]] if legal["evidence_document_id"] else []
        due_conflicts = [
            task for task in tasks
            if task.due > legal["work_must_finish_by"] and task.recordedState.casefold() == "open"
        ]
        critical_path.append(CriticalPathStep(
            id=legal["workload_id"],
            order=len(critical_path) + 1,
            title="Complete legal/procurement review",
            owner=legal_owner,
            due=legal["work_must_finish_by"],
            status="At risk" if due_conflicts else "Required",
            dependency=legal["dependency_ids"].replace(";", "; ") or "None recorded",
            detail=(
                f"Finish before the reviewer is unavailable. "
                f"Available capacity is {legal['available_capacity_hours']} hours against "
                f"{legal['committed_work_hours']} hours already committed."
                + (
                    " An open dependent task is due after the legal finish-by date."
                    if due_conflicts else ""
                )
            ),
            evidenceRefs=legal_refs,
        ))
        step_order = len(critical_path) + 1

    submission_refs = [submission["evidence_document_id"]] if submission and submission["evidence_document_id"] else []
    if submission:
        eligibility_failed = any(item.status == "not_met" for item in criteria)
        critical_path.append(CriticalPathStep(
            id=submission["submission_id"],
            order=len(critical_path) + 1,
            title=(
                "Keep application unsubmitted; reconsider only if eligibility evidence changes"
                if eligibility_failed
                else "Verify remaining requirements, obtain authorized decision, and submit"
            ),
            owner=_person(submission["proposal_owner_id"], people),
            due=None if eligibility_failed else submission["deadline"],
            status="Blocked by evidenced eligibility failure" if eligibility_failed else submission["submission_state"],
            dependency=submission["dependency_ids"].replace(";", "; ") or "None recorded",
            detail=(
                (
                    f"Current blocker: {submission['blockers']} "
                    f"{submission['unknown_requirements']} "
                    "Do not prepare or submit an application unless authoritative evidence changes "
                    "the failed criterion."
                    if eligibility_failed
                    else (
                        f"Required artifacts: {submission['required_artifacts']}. "
                        f"Blockers: {submission['blockers']}. Unknown: {submission['unknown_requirements']} "
                        "No submission is represented as complete."
                    )
                )
            ),
            evidenceRefs=submission_refs,
        ))

    if approval:
        current_status = approval["decision"]
        decision_refs = [approval["evidence_document_id"]] if approval["evidence_document_id"] else []
    else:
        current_status = status
        decision_refs = []
    if slots and partner_required:
        decision_limit = (
            "The available review slot is not a booking or an unconditional final approval; the "
            "current partner letter is due after the Nov 19 slot."
        )
    elif slots:
        decision_limit = "The available review slot is not a booking or funding approval."
    else:
        decision_limit = "This workflow status is not a funding award or submission approval."
    rationale.append(FundingRationale(
        heading="Recorded human status and limitations",
        text=(
            f"The latest recorded status is {current_status}. "
            f"{recommendation} {decision_limit} Remaining evidence and any portal requirements "
            "require human verification."
        ),
        evidenceRefs=sorted(set(decision_refs + executive_refs + legal_refs + submission_refs)),
    ))

    match_required_line = f"${required_match:,} required against ${eligible_cost:,} eligible costs"
    eligibility_answer = " ".join(
        f"{item.text} [{item.status}]" for item in criteria
    )
    program_rationale = next(
        (item.text for item in rationale if item.heading in {
            "Why conditional pursuit may be worthwhile", "Program and community context"
        }),
        "No program or community rationale is documented for this opportunity.",
    )
    next_action_answer = "; ".join(
        f"{step.order}. {step.title}"
        + (f" — {step.owner.display}" if step.owner else "")
        + (f", due {step.due}" if step.due else "")
        for step in critical_path
    )
    summary = (
        f"{notice_id} ({opportunity['title']}) as of {scenario_date.isoformat()}, due "
        f"{opportunity['deadline']} {opportunity['deadline_timezone']} ({deadline_days} days). "
        f"Eligibility/readiness: {eligibility_answer} "
        f"Amendment {amendment['version']} match is {match_required_line}; "
        f"${confirmed_match:,} is confirmed and ${proposed_match:,} is proposed but excluded, "
        f"leaving ${match_gap:,}. {partner_evidence} "
        f"Should we pursue? {recommendation} {program_rationale} "
        f"The dated human disposition remains {current_status}; this is not funding approval. "
        f"Next: {next_action_answer}. "
        f"{decision_limit} Confirm unverified requirements "
        f"({submission['unknown_requirements'] if submission else 'not recorded'}) "
        f"{'before submission' if 'not_met' not in statuses else 'before any reconsideration'}."
    )
    bottom_line = (
        f"{current_status} is the recorded human status. {decision_limit} {recommendation} "
        f"The application remains {submission['submission_state'] if submission else 'status unknown'}."
    )
    rationale_refs = sorted({
        ref for item in rationale for ref in item.evidenceRefs if ref in evidence_by_id
    })
    answer_refs = sorted({
        *rationale_refs,
        *(ref for criterion in criteria for ref in criterion.evidenceRefs if ref in evidence_by_id),
        *(ref for step in critical_path for ref in step.evidenceRefs if ref in evidence_by_id),
    })
    source_states = source_states or {}
    source_labels = {
        Source.FOUNDRY: "Foundry IQ",
        Source.FABRIC: "Fabric IQ",
        Source.WORK: "Work IQ",
        Source.WEB: "External evidence",
    }
    source_descriptions = {
        Source.FOUNDRY: "Funding notice, amendment, eligibility and policy documents",
        Source.FABRIC: "Funding operations, financial, community and program tables",
        Source.WORK: "Proposal tasks, human reviews, messages and staff schedules",
        Source.WEB: "Locally cached synthetic agency guidance; not a live web result",
    }
    source_map = []
    for source in Source:
        refs = [
            row["document_id"] for row in (documents[item] for item in selected_docs if item in documents)
            if row["source"] == source.value
        ]
        source_map.append({
            "source": source.value,
            "label": source_labels[source],
            "status": source_states.get(source, "complete" if refs else "needs_review"),
            "queries": [query or f"{notice_id} funding readiness"],
            "citations": refs,
            "durationMs": 0,
            "retrieving": source_descriptions[source],
            "evidenceCount": len(refs),
            "evidenceNoun": "sources",
            "summary": (
                f"Retrieved {len(refs)} synthetic, versioned evidence item(s)."
                if refs else "No synthetic evidence is available for this source and opportunity."
            ),
        })

    unresolved = [item for item in criteria if item.status == "unknown"]
    missed = [item for item in criteria if item.status == "not_met"]
    if missed:
        eligibility = "Not eligible on at least one evidenced criterion"
    elif unresolved:
        eligibility = "Applicant criteria evidenced; application readiness remains conditional"
    else:
        eligibility = "Modeled eligibility criteria met; confirm any remaining notice requirements"

    trace = [
        {"step": "Selected funding opportunity from the question", "source": "fabric", "detail": f"Matched {notice_id} using the linked opportunity registry.", "ts": 0, "status": "completed"},
        {"step": "Applied latest effective notice terms", "source": "foundry", "detail": f"Amendment {amendment['version']} effective {amendment['effective_date']} controls as of {scenario_date}.", "ts": 1, "status": "completed"},
        {"step": "Reconciled budget and unique match allocations", "source": "fabric", "detail": f"Eligible costs ${eligible_cost:,}; confirmed ${confirmed_match:,}; proposed excluded ${proposed_match:,}; gap ${match_gap:,}.", "ts": 2, "status": "completed"},
        {"step": "Reviewed program fit, decision, and critical path", "source": "work", "detail": f"Preserved the dated human status {current_status}; derived readiness steps from linked task, review, and schedule records.", "ts": 3, "status": "completed"},
        {"step": "Prepared human-review assessment", "detail": "No approval, meeting booking, notification, task submission, or application submission was performed.", "ts": 4, "status": "completed"},
    ]
    return FundingAssessment(
        question=query,
        answer=summary,
        bottomLine=bottom_line,
        opportunity=FundingOpportunity(
            id=notice_id,
            programId=opportunity["program_id"],
            projectId=opportunity["project_id"],
            title=opportunity["title"],
            agency=opportunity["agency"],
            deadline=opportunity["deadline"],
            deadlineTimezone=opportunity["deadline_timezone"],
            asOfDate=opportunity["as_of_date"],
            eligibleCostBasis=eligible_cost,
            requestedAmount=requested_amount,
            projectCostBasis=basis_detail,
        ),
        pursuitStatus=current_status,
        recommendation=recommendation,
        eligibility=eligibility,
        amendmentSummary=(
            f"Amendment {amendment['version']} published {amendment['published_date']}, "
            f"effective {amendment['effective_date']}: {amendment['changed_conditions']}"
        ),
        matchBasis=(
            f"{Decimal(amendment['match_rate'])*100:.0f}% of {match_basis}; {basis_detail}"
        ),
        matchRequired=required_match,
        matchConfirmed=confirmed_match,
        matchProposed=proposed_match,
        matchGap=match_gap,
        deadlineDays=deadline_days,
        criteria=criteria,
        rationale=rationale,
        partner=(
            partner["name"] if partner
            else "Regional partner"
            if amendment["regional_partner_required"].casefold() != "true"
            else "No partner record"
        ),
        partnerEvidence=partner_evidence,
        tasks=tasks,
        criticalPath=critical_path,
        executiveReview=executive_review,
        legalConstraint=legal_constraint,
        submissionStatus=submission["submission_state"] if submission else "Unknown",
        unknownRequirements=submission["unknown_requirements"] if submission else "Submission requirements are not recorded.",
        evidence=evidence,
        answerRefs=answer_refs,
        sourceMap=source_map,
        trace=trace,
    )
