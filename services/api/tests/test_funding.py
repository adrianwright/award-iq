from __future__ import annotations

import csv
import json
from pathlib import Path
from shutil import copytree

from fastapi.testclient import TestClient

from app.config import get_settings
from app.funding import assess_funding
from app.main import app

NOTICE_ID = "FO-2026-117"
QUESTION = (
    "A new infrastructure and community-resilience grant closes in 30 days. Amendment 2 raises "
    "the local match to 25% and adds a regional-partner requirement. Are we eligible, should we "
    "pursue it, and what must happen next?"
)


def _settings_for(data_dir: Path):
    return get_settings().model_copy(update={"DATA_DIR": data_dir})


def _copy_funding_data(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    copytree(get_settings().DATA_DIR, target)
    return target


def _edit_csv(path: Path, edit) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        headers = list(rows[0])
    rows = edit(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _add_current_letter(data_dir: Path) -> str:
    document_id = "DOC-FO117-RTA-LETTER-2026"
    filename = "FO-2026-117_RTA_commitment_letter_v1.md"
    path = data_dir / "work" / filename
    path.write_text(
        "---\ntitle: Synthetic current RTA commitment letter\nnotice_id: FO-2026-117\n"
        "date: 2026-11-16\nsynthetic: true\n---\n\n"
        "Counterfactual only: current signed partner commitment received.\n",
        encoding="utf-8",
    )
    documents_path = data_dir / "fabric" / "funding_ops" / "source_documents.csv"

    def add_document(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        rows.append({
            "document_id": document_id,
            "notice_id": NOTICE_ID,
            "title": "Synthetic current partner letter",
            "source": "work",
            "source_type": "Counterfactual partner letter",
            "filename": filename,
            "version": "1",
            "publication_date": "2026-11-16",
            "effective_from": "2026-11-16",
            "supersedes": "",
            "summary": "Test-only current signed commitment letter.",
        })
        return rows

    _edit_csv(documents_path, add_document)
    return document_id


def test_hero_answer_synthesizes_eligibility_pursuit_and_ordered_next_steps() -> None:
    result = assess_funding(get_settings(), QUESTION)

    assert result.opportunity.id == NOTICE_ID
    assert result.opportunity.asOfDate == "2026-11-16"
    assert result.opportunity.deadline == "2026-12-16"
    assert result.opportunity.deadlineTimezone == "America/New_York"
    assert result.deadlineDays == 30
    assert result.opportunity.eligibleCostBasis == 9_000_000
    assert result.opportunity.requestedAmount == 6_750_000
    assert result.matchRequired == 2_250_000
    assert result.matchConfirmed == 1_800_000
    assert result.matchProposed == 450_000
    assert result.matchGap == 450_000
    assert result.pursuitStatus == "Pursue - pending"
    assert result.submissionStatus == "Not submitted"
    assert "baseline 35" in result.answer
    assert "proposed target 70 percent" in result.answer
    assert "18,400 people" in result.answer
    assert "outcome is unknown" in result.answer
    assert "TASK-117-MATCH" in result.answer
    assert "TASK-117-PARTNER" in result.answer
    assert "2026-11-19" in result.answer
    assert "legal/procurement review" in result.answer
    assert "not a booking or an unconditional final approval" in result.answer
    assert all(task.status == "Drafted (not submitted)" for task in result.tasks)


def test_hero_workflow_owners_timezone_deadlines_and_dependencies() -> None:
    result = assess_funding(get_settings(), QUESTION)
    tasks = {task.id: task for task in result.tasks}
    steps = {step.id: step for step in result.criticalPath}

    assert tasks["TASK-117-MATCH"].owner.id == "FIN-02"
    assert tasks["TASK-117-MATCH"].owner.display == "Maria Santos"
    assert tasks["TASK-117-MATCH"].due == "2026-11-18"
    assert tasks["TASK-117-PARTNER"].owner.id == "PM-01"
    assert tasks["TASK-117-PARTNER"].owner.display == "Jordan Lee"
    assert tasks["TASK-117-PARTNER"].due == "2026-11-20"
    assert tasks["TASK-117-PARTNER"].dependencyIds == ["SLOT-EXEC-FO117-20261119"]
    assert "2026-11-19" in result.executiveReview
    assert "10:00-11:00" in result.executiveReview
    assert "America/New_York (EST, UTC-05:00)" in result.executiveReview
    assert "not booked" in result.executiveReview
    assert "2026-11-23 through 2026-11-27" in result.legalConstraint
    assert "2026-11-20" in result.legalConstraint
    assert steps["SLOT-EXEC-FO117-20261119"].due == "2026-11-19"
    assert steps["WORKLOAD-LEGAL-FO117"].due == "2026-11-20"


def test_missing_partner_letter_is_unknown_and_historical_letter_is_only_a_lead() -> None:
    result = assess_funding(get_settings(), "Is FO-2026-117's current partner letter present?")
    partner_criterion = next(item for item in result.criteria if "partner letter" in item.text.lower())

    assert partner_criterion.status == "unknown"
    assert "missing" in result.partnerEvidence
    prior = next(item for item in result.evidence if item.refId == "DOC-FO117-PRIOR24")
    assert "2024" in prior.title
    assert "historical" in prior.snippet.lower()


def test_non_hero_match_question_returns_data_backed_gap() -> None:
    result = assess_funding(get_settings(), "How much confirmed match is still missing?")

    assert "$450,000" in result.answer
    assert result.matchGap == 450_000
    assert "Pursue - pending" in result.answer


def test_ready_and_failed_comparators_return_distinct_findings() -> None:
    ready = assess_funding(get_settings(), "Is FO-2026-204 ready to submit?")
    failed = assess_funding(get_settings(), "Which requirement fails for FO-2026-330?")

    assert ready.opportunity.id == "FO-2026-204"
    assert ready.matchRequired == 100_000
    assert ready.matchGap == 0
    assert ready.pursuitStatus == "Ready to submit"
    assert ready.eligibility.startswith("Modeled eligibility criteria met")
    assert ready.submissionStatus == "Not submitted"
    ready_context = next(
        item for item in ready.rationale if item.heading == "Program and community context"
    )
    assert "prior partner experience" not in ready_context.text
    assert "not achieved results" in ready_context.text
    assert failed.opportunity.id == "FO-2026-330"
    assert any(item.status == "not_met" and "Pine County" in item.text for item in failed.criteria)
    assert failed.eligibility == "Not eligible on at least one evidenced criterion"
    assert "Do not pursue" in failed.recommendation
    failed_readiness = next(
        item for item in failed.rationale if item.heading == "Eligibility and readiness"
    )
    assert "No current regional-partner letter is required" in failed_readiness.text
    assert "letter is not documented" not in failed_readiness.text
    assert failed.partner == "Regional partner"
    assert "does not require a regional-partner commitment letter" in failed.partnerEvidence
    assert "No partner record is present" not in failed.answer
    assert "other criterion/criteria remain unknown" not in failed.recommendation
    assert "final approval" not in failed.answer
    blocked_submission = next(
        step for step in failed.criticalPath if step.id == "SUBMISSION-FO330"
    )
    assert blocked_submission.due is None
    assert blocked_submission.status == "Blocked by evidenced eligibility failure"
    assert "Keep application unsubmitted" in blocked_submission.title
    assert "Verify remaining requirements, obtain authorized decision, and submit" not in failed.answer
    fabric_source = next(item for item in failed.sourceMap if item["source"] == "fabric")
    assert "DOC-FO330-STRUCTURED" in fabric_source["citations"]


def test_stream_reports_only_retrieved_fixture_citations_as_complete() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/funding/ask/stream",
        json={"question": "Which requirement fails for FO-2026-330?"},
    )

    assert response.status_code == 200
    events = [
        json.loads(data)
        for block in response.text.split("\n\n")
        for line in block.splitlines()
        if line.startswith("data: ")
        for data in [line.removeprefix("data: ")]
    ]
    results = {item["source"]: item for item in events if "source" in item and "summary" in item}
    assert results["foundry"]["status"] == "complete"
    assert results["fabric"]["status"] == "complete"
    assert results["work"]["status"] == "complete"
    assert results["web"]["status"] == "needs_review"
    assert results["web"]["citations"] == []


def test_assessment_citations_resolve_and_include_provenance() -> None:
    client = TestClient(app)
    response = client.post("/api/funding/ask", json={"question": QUESTION})

    assert response.status_code == 200
    payload = response.json()
    refs = {item["refId"] for item in payload["evidence"]}
    assert set(payload["answerRefs"]) <= refs
    for item in payload["evidence"]:
        evidence = client.get(item["url"])
        assert evidence.status_code == 200
        assert "Award IQ synthetic source document" in evidence.text
        assert "published" in item["sourceType"]


def test_future_amendment_does_not_override_current_effective_version(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "amendments.csv"

    def add_future(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        future = rows[1].copy()
        future.update({
            "amendment_id": "AMD-FO117-03",
            "version": "3",
            "published_date": "2026-12-01",
            "effective_date": "2026-12-01",
            "predecessor_id": "AMD-FO117-02",
            "changed_conditions": "Future planned 30% match.",
            "match_rate": "0.30",
            "status": "Planned",
        })
        rows.append(future)
        return rows

    _edit_csv(path, add_future)
    result = assess_funding(_settings_for(data_dir), QUESTION)
    assert result.matchRequired == 2_250_000
    assert result.pursuitStatus == "Pursue - pending"


def test_new_effective_amendment_changes_match_requirement_and_request(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "amendments.csv"

    def raise_match(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        rows[1]["match_rate"] = "0.30"
        rows[1]["changed_conditions"] = "Counterfactual Amendment 2 requires 30% match."
        return rows

    _edit_csv(path, raise_match)
    result = assess_funding(_settings_for(data_dir), QUESTION)
    match_criterion = next(item for item in result.criteria if "match" in item.text.lower())
    assert result.matchRequired == 2_700_000
    assert result.matchGap == 900_000
    assert result.opportunity.requestedAmount == 6_300_000
    assert "30% local match" in match_criterion.text
    assert match_criterion.status == "unknown"


def test_confirming_proposed_reserve_recomputes_match_but_keeps_human_status(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "match_sources.csv"

    def confirm_reserve(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        next(row for row in rows if row["allocation_id"] == "ALLOC-RESERVE-CANDIDATE-FO117")["status"] = "Confirmed"
        return rows

    _edit_csv(path, confirm_reserve)
    result = assess_funding(_settings_for(data_dir), QUESTION)
    match_criterion = next(item for item in result.criteria if "local match" in item.text.lower())
    assert result.matchConfirmed == 2_250_000
    assert result.matchGap == 0
    assert match_criterion.status == "met"
    assert result.pursuitStatus == "Pursue - pending"


def test_removed_confirmed_allocation_expands_gap_and_proposed_is_not_counted(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "match_sources.csv"

    def remove_confirmed(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        return [row for row in rows if row["allocation_id"] != "ALLOC-CAPITAL-2026-FO117"]

    _edit_csv(path, remove_confirmed)
    result = assess_funding(_settings_for(data_dir), QUESTION)
    assert result.matchConfirmed == 0
    assert result.matchProposed == 450_000
    assert result.matchGap == 2_250_000


def test_receiving_current_letter_resolves_partner_criterion_and_cites_it(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    letter_id = _add_current_letter(data_dir)
    path = data_dir / "fabric" / "funding_ops" / "partners.csv"

    def receive_letter(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        rows[0]["commitment_status"] = "Received"
        rows[0]["letter_document_id"] = letter_id
        rows[0]["letter_date"] = "2026-11-16"
        return rows

    _edit_csv(path, receive_letter)
    result = assess_funding(_settings_for(data_dir), QUESTION)
    criterion = next(item for item in result.criteria if "partner letter" in item.text.lower())
    assert criterion.status == "met"
    assert letter_id in criterion.evidenceRefs
    assert "received" in result.partnerEvidence
    assert result.pursuitStatus == "Pursue - pending"


def test_missing_partner_record_stays_unknown_not_not_met(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "partners.csv"
    _edit_csv(path, lambda rows: [])

    result = assess_funding(_settings_for(data_dir), QUESTION)
    criterion = next(item for item in result.criteria if "partner letter" in item.text.lower())
    assert criterion.status == "unknown"
    assert "No partner record is present" in result.partnerEvidence


def test_task_due_after_legal_finish_by_is_flagged_at_risk(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "proposal_tasks.csv"

    def delay_partner_task(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        next(row for row in rows if row["task_id"] == "TASK-117-PARTNER")["due_date"] = "2026-11-24"
        return rows

    _edit_csv(path, delay_partner_task)
    result = assess_funding(_settings_for(data_dir), QUESTION)
    partner_task = next(task for task in result.tasks if task.id == "TASK-117-PARTNER")
    legal_step = next(step for step in result.criticalPath if step.id == "WORKLOAD-LEGAL-FO117")
    assert partner_task.due == "2026-11-24"
    assert legal_step.status == "At risk"
    assert "due after the legal finish-by date" in legal_step.detail


def test_changed_legal_finish_by_changes_schedule_risk(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "staff_workload.csv"

    def shorten_review_window(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        next(row for row in rows if row["workload_id"] == "WORKLOAD-LEGAL-FO117")["work_must_finish_by"] = "2026-11-18"
        return rows

    _edit_csv(path, shorten_review_window)
    result = assess_funding(_settings_for(data_dir), QUESTION)
    legal_step = next(step for step in result.criticalPath if step.id == "WORKLOAD-LEGAL-FO117")
    assert result.legalConstraint.endswith("2026-11-18.")
    assert legal_step.status == "At risk"
