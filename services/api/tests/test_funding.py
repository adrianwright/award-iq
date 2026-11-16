from __future__ import annotations

import csv
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


def test_current_amendment_controls_match_and_pending_decision() -> None:
    result = assess_funding(get_settings(), QUESTION)

    assert result.opportunity.id == NOTICE_ID
    assert result.opportunity.asOfDate == "2026-11-16"
    assert result.opportunity.deadline == "2026-12-16"
    assert result.deadlineDays == 30
    assert result.matchRequired == 2_250_000
    assert result.matchConfirmed == 1_800_000
    assert result.matchProposed == 450_000
    assert result.matchGap == 450_000
    assert result.pursuitStatus == "Pursue - pending"
    assert result.submissionStatus == "Not submitted"
    assert all(task.status == "Drafted (not submitted)" for task in result.tasks)


def test_funding_assessment_preserves_owners_and_scheduling_constraints() -> None:
    result = assess_funding(get_settings(), QUESTION)
    tasks = {task.id: task for task in result.tasks}

    assert tasks["TASK-117-MATCH"].owner.id == "FIN-02"
    assert tasks["TASK-117-MATCH"].owner.display == "Maria Santos"
    assert tasks["TASK-117-MATCH"].due == "2026-11-18"
    assert tasks["TASK-117-PARTNER"].owner.id == "PM-01"
    assert tasks["TASK-117-PARTNER"].owner.display == "Jordan Lee"
    assert tasks["TASK-117-PARTNER"].due == "2026-11-20"
    assert "2026-11-19" in result.executiveReview
    assert "10:00-11:00" in result.executiveReview
    assert "UTC-08:00" in result.executiveReview
    assert "2026-11-23 through 2026-11-27" in result.legalConstraint
    assert "2026-11-20" in result.legalConstraint
    assert "not booked" in result.executiveReview


def test_missing_partner_letter_is_unresolved_and_history_is_not_current_evidence() -> None:
    result = assess_funding(get_settings(), "Is the regional partner requirement satisfied?")
    partner_criterion = next(item for item in result.criteria if "partner" in item.text.lower())

    assert partner_criterion.status == "uncertain"
    assert "no current commitment letter is present" in result.partnerEvidence
    evidence = {item.refId: item for item in result.evidence}
    assert any("2024" in evidence[ref].title for ref in partner_criterion.evidenceRefs)


def test_non_hero_match_question_returns_grounded_gap() -> None:
    result = assess_funding(get_settings(), "How much confirmed match is still missing?")

    assert "$450,000" in result.answer
    assert result.matchGap == 450_000
    assert "Pursue - pending" in result.answer


def test_assessment_citations_resolve_to_synthetic_evidence() -> None:
    client = TestClient(app)
    result = client.post("/api/funding/ask", json={"question": QUESTION})

    assert result.status_code == 200
    payload = result.json()
    refs = {item["refId"] for item in payload["evidence"]}
    assert set(payload["answerRefs"]) <= refs
    for item in payload["evidence"]:
        response = client.get(item["url"])
        assert response.status_code == 200
        assert "Award IQ synthetic source document" in response.text


def test_current_match_is_derived_from_current_amendment() -> None:
    funding_dir = get_settings().DATA_DIR / "fabric" / "funding_ops"
    with (funding_dir / "amendments.csv").open(newline="", encoding="utf-8") as handle:
        amendments = list(csv.DictReader(handle))
    current = max(
        (row for row in amendments if row["notice_id"] == NOTICE_ID),
        key=lambda row: row["effective_date"],
    )
    assert current["amendment"] == "2"
    assert current["match_rate"] == "0.25"
    assert current["regional_partner_required"] == "true"


def _copy_funding_data(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    copytree(get_settings().DATA_DIR, target)
    return target


def test_future_amendment_does_not_override_current_effective_version(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "amendments.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        headers = list(rows[0])
    rows.append({
        "notice_id": NOTICE_ID,
        "amendment": "3",
        "published_date": "2026-12-01",
        "effective_date": "2026-12-01",
        "status": "Planned",
        "match_rate": "0.30",
        "regional_partner_required": "true",
        "supersedes": "2",
    })
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    result = assess_funding(
        get_settings().model_copy(update={"DATA_DIR": data_dir}),
        QUESTION,
    )
    assert result.matchRequired == 2_250_000
    assert result.pursuitStatus == "Pursue - pending"


def test_proposed_match_does_not_reduce_confirmed_gap(tmp_path: Path) -> None:
    data_dir = _copy_funding_data(tmp_path)
    path = data_dir / "fabric" / "funding_ops" / "match_sources.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        headers = list(rows[0])
    proposed = next(row for row in rows if row["status"] == "Proposed")
    proposed["amount"] = "999999"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    result = assess_funding(
        get_settings().model_copy(update={"DATA_DIR": data_dir}),
        QUESTION,
    )
    assert result.matchProposed == 999_999
    assert result.matchConfirmed == 1_800_000
    assert result.matchGap == 450_000
