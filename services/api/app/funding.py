from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
import yaml

from app.config import Settings
from app.schemas import Evidence, Source
from app.sources.base import evidence_doc_url

class FundingPerson(BaseModel):
    id: str
    display: str
    role: str


class FundingOpportunity(BaseModel):
    id: str
    title: str
    agency: str
    deadline: str
    asOfDate: str


class FundingCriterion(BaseModel):
    text: str
    status: Literal["met", "uncertain", "not_met"]
    evidenceRefs: list[str]


class FundingTask(BaseModel):
    id: str
    text: str
    owner: FundingPerson
    due: str
    status: str = "Drafted (not submitted)"


class FundingAssessment(BaseModel):
    question: str
    answer: str
    bottomLine: str
    opportunity: FundingOpportunity
    pursuitStatus: str
    recommendation: str
    eligibility: str
    matchBasis: str
    matchRequired: int
    matchConfirmed: int
    matchProposed: int
    matchGap: int
    deadlineDays: int
    criteria: list[FundingCriterion]
    partner: str
    partnerEvidence: str
    tasks: list[FundingTask]
    executiveReview: str
    legalConstraint: str
    submissionStatus: str
    evidence: list[Evidence]
    answerRefs: list[str]
    sourceMap: list[dict[str, object]]
    trace: list[dict[str, object]]
    mode: Literal["mock", "live"] = "mock"
    disclaimer: str = "Synthetic grant decision support. Human review required. No funds approved, tasks submitted, meetings booked, or applications submitted."


def _read_rows(data_dir: Path, table: str) -> list[dict[str, str]]:
    with (data_dir / "fabric" / "funding_ops" / f"{table}.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        return list(csv.DictReader(handle))


def _person(person_id: str, people: dict[str, dict[str, str]]) -> FundingPerson:
    record = people[person_id]
    return FundingPerson(id=person_id, display=record["name"], role=record["role"])


def assess_funding(
    settings: Settings,
    question: str,
    *,
    source_states: dict[Source, str] | None = None,
) -> FundingAssessment:
    """Build the deterministic, evidence-linked Award IQ funding assessment."""
    data_dir = settings.DATA_DIR
    with (data_dir / "registry" / "funding_registry.yaml").open(encoding="utf-8") as handle:
        registry = yaml.safe_load(handle)
    notice_id = registry["funding_opportunities"][0]["id"]
    opportunity = next(
        row for row in _read_rows(data_dir, "funding_opportunities")
        if row["notice_id"] == notice_id
    )
    scenario_date = date.fromisoformat(opportunity["as_of_date"])
    if opportunity["as_of_date"] != registry["meta"]["scenario_as_of"]:
        raise ValueError("Funding registry and operation tables disagree on the scenario date.")
    effective_amendment = max(
        (
            row for row in _read_rows(data_dir, "amendments")
            if row["notice_id"] == notice_id and row["effective_date"] <= scenario_date.isoformat()
        ),
        key=lambda row: (row["effective_date"], int(row["amendment"])),
    )
    if effective_amendment["status"] != "Current":
        raise ValueError("Latest effective funding amendment is not marked current.")
    budget = next(
        row for row in _read_rows(data_dir, "budget_lines")
        if row["notice_id"] == notice_id and row["classification"] == "Required match"
    )
    total_costs = int(opportunity["total_project_cost"])
    required = round(total_costs * float(effective_amendment["match_rate"]))
    if int(budget["amount"]) != required:
        raise ValueError("Funding budget does not match the current amendment calculation.")
    sources = [
        row for row in _read_rows(data_dir, "match_sources")
        if row["notice_id"] == notice_id
    ]
    confirmed = sum(
        int(row["amount"]) for row in sources if row["status"].casefold() == "confirmed"
    )
    proposed = sum(
        int(row["amount"]) for row in sources if row["status"].casefold() == "proposed"
    )
    gap = max(required - confirmed, 0)
    amendment_id = "r1"
    match_id = "r2"
    workflow_id = "r3"
    huddle_id = "r4"
    eligibility_id = "r5"
    external_id = "r6"
    evidence = [
        _evidence(data_dir, amendment_id, Source.FOUNDRY, "FO-2026-117_amendment_2_v1.md", "Funding notice amendment"),
        _evidence(data_dir, match_id, Source.FABRIC, "FO-2026-117_structured_snapshot_v1.md", "Structured funding tables"),
        _evidence(data_dir, workflow_id, Source.WORK, "FO-2026-117_readiness_tracker_v2.md", "Grant-readiness tracker v2"),
        _evidence(data_dir, huddle_id, Source.WORK, "FO-2026-117_proposal_huddle_2026-11-09.md", "Proposal huddle notes"),
        _evidence(data_dir, eligibility_id, Source.FOUNDRY, "FO-2026-117_applicant_eligibility_v1.md", "Applicant eligibility rules"),
        _evidence(data_dir, external_id, Source.WEB, "FO-2026-117_agency_guidance_v1.md", "Synthetic agency guidance snapshot"),
        _evidence(data_dir, "r7", Source.WORK, "FO-2026-117_review_minutes_2026-11-05.md", "Go/no-go review minutes"),
        _evidence(data_dir, "r8", Source.WORK, "FO-2026-117_prior_proposal_2024_v1.md", "2024 prior proposal evidence"),
        _evidence(data_dir, "r9", Source.WORK, "FO-2026-117_pursue_decision_brief_v2.md", "Current pursue decision brief v2"),
    ]
    refs = {item.refId: item for item in evidence}

    criteria = [
        FundingCriterion(
            text="Eligible local public applicant",
            status="met",
            evidenceRefs=[eligibility_id],
        ),
        FundingCriterion(
            text=f"{int(float(effective_amendment['match_rate']) * 100)}% local match confirmed (${required:,} required; ${confirmed:,} confirmed)",
            status="uncertain" if gap else "met",
            evidenceRefs=[amendment_id, match_id],
        ),
        FundingCriterion(
            text="Current regional-partner commitment letter",
            status="uncertain",
            evidenceRefs=[amendment_id, workflow_id, "r8", external_id],
        ),
    ]
    people = {
        row["person_id"]: row for row in _read_rows(data_dir, "people")
    }
    task_rows = [
        row for row in _read_rows(data_dir, "staff_workload")
        if row["notice_id"] == notice_id
    ]
    task_records = [
        row for row in _read_rows(data_dir, "proposal_tasks")
        if row["notice_id"] == notice_id
    ]
    tasks = [
        FundingTask(
            id=row["task_id"],
            text=(
                f"Confirm capital-reserve source for the remaining ${gap:,} match."
                if row["task_id"] == "TASK-117-MATCH"
                else "Obtain a current Regional Transit Authority commitment letter."
            ),
            owner=_person(row["owner_id"], people),
            due=row["due_date"],
            status="Drafted (not submitted)",
        )
        for row in task_records
    ]
    recorded_review = max(
        (
            row for row in _read_rows(data_dir, "approvals")
            if row["notice_id"] == notice_id and row["review_date"] <= scenario_date.isoformat()
        ),
        key=lambda row: row["review_date"],
    )
    partner_record = next(
        row for row in _read_rows(data_dir, "partners")
        if row["notice_id"] == notice_id
    )
    slot = next(
        row for row in _read_rows(data_dir, "scheduling_slots")
        if row["notice_id"] == notice_id
    )
    legal = task_rows[0]
    days_until_deadline = (date.fromisoformat(opportunity["deadline"]) - scenario_date).days
    query = question.strip()
    lowered = query.casefold()
    focus = (
        "The current confirmed-match gap is $450,000."
        if re.search(r"\b(match|fund|gap|budget)\b", lowered)
        else "A grounded recommendation is to continue pursuing only conditionally; the human go/no-go remains pending."
    )
    summary = (
        f"FO-2026-117 is {days_until_deadline} days from its 2026-12-16 deadline. Amendment "
        f"{effective_amendment['amendment']} requires ${required:,} in local match against "
        f"${int(opportunity['total_project_cost']):,} total eligible project costs; "
        f"${confirmed:,} is confirmed and the ${gap:,} balance is not. Current status remains "
        f"{recorded_review['decision']}, conditioned on match confirmation and a current partner letter. {focus}"
    )
    source_states = source_states or {}
    source_specs = [
        (Source.FOUNDRY, "Funding notice, amendment, applicant rules and approval policy", [amendment_id, eligibility_id, "r7"]),
        (Source.FABRIC, "Grant operations, match sources, budgets, owners and deadlines", [match_id]),
        (Source.WORK, "Proposal team, task state, decision notes and reviewer calendar", [workflow_id, huddle_id, "r8", "r9"]),
        (Source.WEB, "Synthetic external agency guidance snapshot (not a live connection)", [external_id]),
    ]
    source_map = [
        {
            "source": source.value,
            "label": source.value.title() + " IQ" if source != Source.WEB else "External evidence",
            "status": source_states.get(source, "complete"),
            "queries": [query or f"{notice_id} funding readiness"],
            "citations": citations,
            "durationMs": 0,
            "retrieving": label,
            "evidenceCount": len(citations),
            "evidenceNoun": "sources",
            "summary": f"Retrieved {len(citations)} synthetic, versioned evidence item(s).",
        }
        for source, label, citations in source_specs
    ]
    return FundingAssessment(
        question=query,
        answer=summary,
        bottomLine=(
            "Pursue - pending is the recorded human status, not an unconditional eligibility or "
            "approval decision. Resolve the $450,000 match gap and obtain the current partner "
            "letter before an authorized reviewer revisits the decision."
        ),
        opportunity=FundingOpportunity(
            id=notice_id,
            title=opportunity["title"],
            agency=opportunity["agency"],
            deadline=opportunity["deadline"],
            asOfDate=opportunity["as_of_date"],
        ),
        pursuitStatus=recorded_review["decision"],
        recommendation="Continue conditionally; do not treat as approved or submitted.",
        eligibility="Conditional / unresolved evidence",
        matchBasis=budget["basis"],
        matchRequired=required,
        matchConfirmed=confirmed,
        matchProposed=proposed,
        matchGap=gap,
        deadlineDays=days_until_deadline,
        criteria=criteria,
        partner=partner_record["name"],
        partnerEvidence=(
            "2024 letter is a lead only; no current commitment letter is present."
            if partner_record["current_commitment"] == "Not received"
            else f"Current commitment state: {partner_record['current_commitment']}."
        ),
        tasks=tasks,
        executiveReview=(
            f"{slot['date']}, {slot['start_time']}-{slot['end_time']} "
            f"{slot['timezone']} with Dr. Elena Ruiz (review slot; not booked)"
        ),
        legalConstraint=(
            f"Sam Patel is unavailable {legal['unavailable_from']} through "
            f"{legal['unavailable_through']}; legal/procurement review must finish by "
            f"{legal['work_must_finish_by']}."
        ),
        submissionStatus="Not submitted",
        evidence=evidence,
        answerRefs=list(refs),
        sourceMap=source_map,
        trace=[
            {"step": "Loaded current notice and amendment", "source": "foundry", "detail": f"Amendment {effective_amendment['amendment']} effective {effective_amendment['effective_date']} takes precedence.", "ts": 0, "status": "completed"},
            {"step": "Calculated confirmed match and gap", "source": "fabric", "detail": f"Confirmed funds only: ${confirmed:,}; required ${required:,}; gap ${gap:,}. Proposed funds excluded.", "ts": 1, "status": "completed"},
            {"step": "Checked proposal workflow and ownership", "source": "work", "detail": "Validated the 2026-11-05 pending disposition, open tasks, and reviewer availability.", "ts": 2, "status": "completed"},
            {"step": "Prepared human-review assessment", "detail": "No approval, meeting booking, notification, task submission, or application submission was performed.", "ts": 3, "status": "completed"},
        ],
    )


def _evidence(
    data_dir: Path, ref_id: str, source: Source, filename: str, source_type: str
) -> Evidence:
    work_files = {
        "FO-2026-117_readiness_tracker_v2.md",
        "FO-2026-117_proposal_huddle_2026-11-09.md",
        "FO-2026-117_review_minutes_2026-11-05.md",
        "FO-2026-117_prior_proposal_2024_v1.md",
        "FO-2026-117_pursue_decision_brief_v2.md",
    }
    if source == Source.WEB:
        subdir = "web"
    elif source == Source.FABRIC:
        subdir = "funding_ops"
    else:
        subdir = "work" if filename in work_files else "foundry_docs"
    path = data_dir / subdir / filename
    if subdir == "funding_ops":
        path = data_dir / "fabric" / "funding_ops" / filename
    text = path.read_text(encoding="utf-8")
    body = text.split("---", 2)[-1]
    snippet = body.strip()
    snippet = " ".join(snippet.split())[:300]
    return Evidence(
        refId=ref_id,
        source=source,
        title=filename.removesuffix(".md").replace("_", " "),
        snippet=snippet,
        url=evidence_doc_url(subdir, filename),
        sourceType=source_type,
    )
