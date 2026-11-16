"""Validate Award IQ funding links, arithmetic, provenance and deterministic generation."""
from __future__ import annotations

import csv
import re
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.fabric.funding_ops.generate import generate as generate_funding_tables

FABRIC_DIR = ROOT / "data" / "fabric"
URL_RE = re.compile(r'https?://[^\s"<>]+')


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_funding_ops() -> list[str]:
    """Validate linked Award IQ funding records, foreign keys, arithmetic, and generation."""
    problems: list[str] = []
    directory = FABRIC_DIR / "funding_ops"
    expected_names = {f"{name}.csv" for name in (
        "amendments", "approvals", "budget_lines", "community_metrics",
        "eligibility_criteria", "funding_opportunities", "match_sources", "organizations",
        "partners", "people", "prior_proposals", "program_performance", "programs",
        "projects", "geographies", "scheduling_slots", "staff_workload", "submissions",
        "proposal_tasks", "source_documents",
    )}
    actual_names = {path.name for path in directory.glob("*.csv")}
    if actual_names != expected_names:
        problems.append(
            f"[funding] table set differs: missing={sorted(expected_names - actual_names)}, "
            f"unexpected={sorted(actual_names - expected_names)}"
        )
        return problems

    tables = {name[:-4]: _read_csv(directory / name) for name in sorted(expected_names)}
    keys = {
        "funding_opportunities": "notice_id", "programs": "program_id", "projects": "project_id",
        "organizations": "organization_id", "geographies": "geography_id",
        "amendments": "amendment_id", "eligibility_criteria": "criterion_id",
        "budget_lines": "line_id", "match_sources": "allocation_id", "partners": "partner_id",
        "people": "person_id", "prior_proposals": "proposal_id", "program_performance": "metric_id",
        "community_metrics": "metric_id", "staff_workload": "workload_id",
        "scheduling_slots": "slot_id", "approvals": "approval_id", "submissions": "submission_id",
        "proposal_tasks": "task_id", "source_documents": "document_id",
    }
    ids: dict[str, set[str]] = {}
    for table, key in keys.items():
        values = [row[key] for row in tables[table]]
        if len(values) != len(set(values)):
            problems.append(f"[funding] {table}.{key} contains duplicate keys")
        ids[table] = set(values)
    if len(tables["funding_opportunities"]) < 3:
        problems.append("[funding] requires hero, ready, and failed-eligibility comparators")

    opportunities = {row["notice_id"]: row for row in tables["funding_opportunities"]}
    if set(opportunities) != {"FO-2026-117", "FO-2026-204", "FO-2026-330"}:
        problems.append("[funding] expected the three named synthetic notice scenarios")
    for notice_id, notice in opportunities.items():
        as_of = date.fromisoformat(notice["as_of_date"])
        deadline = date.fromisoformat(notice["deadline"])
        if notice_id == "FO-2026-117" and (
            as_of.isoformat(), deadline.isoformat(), notice["deadline_timezone"]
        ) != ("2026-11-16", "2026-12-16", "America/New_York"):
            problems.append("[funding] hero scenario date, deadline, or timezone drifted")
        if notice["program_id"] not in ids["programs"] or notice["project_id"] not in ids["projects"]:
            problems.append(f"[funding] {notice_id} has a dangling program or project reference")
        if notice["applicant_org_id"] not in ids["organizations"] or notice["geography_id"] not in ids["geographies"]:
            problems.append(f"[funding] {notice_id} has a dangling applicant or geography reference")
        amendment_rows = [
            row for row in tables["amendments"]
            if row["notice_id"] == notice_id and date.fromisoformat(row["effective_date"]) <= as_of
        ]
        latest = max(amendment_rows, key=lambda row: (row["effective_date"], int(row["version"]))) if amendment_rows else None
        if latest is None:
            problems.append(f"[funding] {notice_id} has no effective amendment")
            continue
        if notice["current_amendment_id"] != latest["amendment_id"]:
            problems.append(f"[funding] {notice_id} current amendment ID does not match effective precedence")
        eligible_costs = sum(
            int(row["amount"]) for row in tables["budget_lines"]
            if row["notice_id"] == notice_id and row["classification"] == "Eligible project cost"
        )
        if eligible_costs != int(notice["total_eligible_cost"]):
            problems.append(f"[funding] {notice_id} eligible budget lines do not reconcile")
        required = int(Decimal(eligible_costs) * Decimal(latest["match_rate"]))
        if notice_id == "FO-2026-117" and (
            latest["version"] != "2" or latest["match_rate"] != "0.25"
            or latest["regional_partner_required"].casefold() != "true"
            or required != 2_250_000 or int(notice["requested_amount"]) != 6_750_000
        ):
            problems.append("[funding] hero Amendment 2 match, partner rule, or $6.75M request drifted")
        allocation_rows = [
            row for row in tables["match_sources"] if row["notice_id"] == notice_id
        ]
        allocation_ids = [row["allocation_id"] for row in allocation_rows]
        if len(allocation_ids) != len(set(allocation_ids)):
            problems.append(f"[funding] {notice_id} repeats a match allocation ID")
        if any(row["status"] not in {"Confirmed", "Proposed", "Rejected"} for row in allocation_rows):
            problems.append(f"[funding] {notice_id} has an invalid match status")
        if notice_id == "FO-2026-117":
            confirmed = sum(int(row["amount"]) for row in allocation_rows if row["status"] == "Confirmed")
            proposed = sum(int(row["amount"]) for row in allocation_rows if row["status"] == "Proposed")
            if (confirmed, proposed, required - confirmed) != (1_800_000, 450_000, 450_000):
                problems.append("[funding] hero confirmed/proposed match arithmetic drifted")

    fk_specs = (
        ("projects", "notice_id", "funding_opportunities"), ("projects", "program_id", "programs"),
        ("projects", "applicant_org_id", "organizations"), ("projects", "geography_id", "geographies"),
        ("organizations", "geography_id", "geographies"),
        ("programs", "evidence_document_id", "source_documents"),
        ("amendments", "notice_id", "funding_opportunities"), ("amendments", "source_document_id", "source_documents"),
        ("eligibility_criteria", "notice_id", "funding_opportunities"), ("eligibility_criteria", "amendment_id", "amendments"),
        ("eligibility_criteria", "evidence_document_id", "source_documents"),
        ("budget_lines", "notice_id", "funding_opportunities"), ("budget_lines", "project_id", "projects"),
        ("budget_lines", "evidence_document_id", "source_documents"),
        ("match_sources", "notice_id", "funding_opportunities"), ("match_sources", "project_id", "projects"),
        ("match_sources", "owner_id", "people"), ("match_sources", "evidence_document_id", "source_documents"),
        ("partners", "partner_org_id", "organizations"), ("partners", "notice_id", "funding_opportunities"),
        ("partners", "evidence_document_id", "source_documents"),
        ("prior_proposals", "partner_id", "partners"), ("prior_proposals", "evidence_document_id", "source_documents"),
        ("program_performance", "program_id", "programs"), ("program_performance", "project_id", "projects"),
        ("program_performance", "source_document_id", "source_documents"),
        ("community_metrics", "program_id", "programs"), ("community_metrics", "geography_id", "geographies"),
        ("community_metrics", "source_document_id", "source_documents"),
        ("staff_workload", "person_id", "people"), ("staff_workload", "notice_id", "funding_opportunities"),
        ("staff_workload", "evidence_document_id", "source_documents"),
        ("scheduling_slots", "reviewer_id", "people"), ("scheduling_slots", "notice_id", "funding_opportunities"),
        ("scheduling_slots", "review_id", "approvals"),
        ("scheduling_slots", "evidence_document_id", "source_documents"),
        ("approvals", "notice_id", "funding_opportunities"), ("approvals", "project_id", "projects"),
        ("approvals", "required_owner_id", "people"), ("approvals", "evidence_document_id", "source_documents"),
        ("submissions", "notice_id", "funding_opportunities"), ("submissions", "project_id", "projects"),
        ("submissions", "proposal_owner_id", "people"), ("submissions", "evidence_document_id", "source_documents"),
        ("proposal_tasks", "notice_id", "funding_opportunities"), ("proposal_tasks", "owner_id", "people"),
    )
    for table, column, target in fk_specs:
        for row in tables[table]:
            value = row[column]
            if value and value not in ids[target]:
                problems.append(f"[funding] {table}.{column} has dangling value {value}")

    amendment_ids = {row["amendment_id"] for row in tables["amendments"]}
    dependency_ids = (
        ids["proposal_tasks"] | ids["scheduling_slots"] | ids["staff_workload"] | ids["approvals"]
    )
    for row in tables["amendments"]:
        if row["predecessor_id"] and row["predecessor_id"] not in amendment_ids:
            problems.append(f"[funding] amendment {row['amendment_id']} has a dangling predecessor")
    for row in tables["partners"]:
        if row["historical_proposal_id"] and row["historical_proposal_id"] not in ids["prior_proposals"]:
            problems.append(f"[funding] partner {row['partner_id']} has a dangling prior proposal")
        if row["letter_document_id"] and row["letter_document_id"] not in ids["source_documents"]:
            problems.append(f"[funding] partner {row['partner_id']} has a dangling current-letter citation")
    for table, key in (
        ("proposal_tasks", "task_id"), ("scheduling_slots", "slot_id"),
        ("staff_workload", "workload_id"), ("submissions", "submission_id"),
    ):
        for row in tables[table]:
            for dependency in filter(None, row["dependency_ids"].split(";")):
                if dependency not in dependency_ids:
                    problems.append(f"[funding] {table}.{key}={row[key]} has dangling dependency {dependency}")
    for row in tables["proposal_tasks"]:
        for document_id in filter(None, row["supporting_document_ids"].split(";")):
            if document_id not in ids["source_documents"]:
                problems.append(f"[funding] task {row['task_id']} has a dangling supporting document")
    for document in tables["source_documents"]:
        source_dir = {
            "foundry": "foundry_docs",
            "fabric": "fabric/funding_ops",
            "work": "work",
            "web": "web",
        }.get(document["source"], "")
        if document["notice_id"] not in opportunities:
            problems.append(f"[funding] document {document['document_id']} has an unknown notice")
        if document["source"] not in {"foundry", "fabric", "work", "web"}:
            problems.append(f"[funding] document {document['document_id']} has an invalid source")
        if document["supersedes"] and document["supersedes"] not in ids["source_documents"]:
            problems.append(f"[funding] document {document['document_id']} has a dangling supersedes ID")
        if not source_dir or not (ROOT / "data" / source_dir / document["filename"]).is_file():
            problems.append(f"[funding] document {document['document_id']} does not resolve to a file")

    hero_tasks = {row["task_id"]: row for row in tables["proposal_tasks"] if row["notice_id"] == "FO-2026-117"}
    expected_tasks = {"TASK-117-MATCH": ("FIN-02", "2026-11-18"), "TASK-117-PARTNER": ("PM-01", "2026-11-20")}
    for task_id, expected in expected_tasks.items():
        task = hero_tasks.get(task_id)
        if task is None or (task["owner_id"], task["due_date"]) != expected or task["status"] != "Open":
            problems.append(f"[funding] {task_id} owner, due date, or open state drifted")
    hero_approval = next((row for row in tables["approvals"] if row["notice_id"] == "FO-2026-117"), None)
    if hero_approval is None or (
        hero_approval["decision"], hero_approval["state"], hero_approval["decision_date"]
    ) != ("Pursue - pending", "Pending", "2026-11-05"):
        problems.append("[funding] hero recorded pursuit disposition is not pending")
    hero_slot = next((row for row in tables["scheduling_slots"] if row["notice_id"] == "FO-2026-117"), None)
    if hero_slot is None or (
        hero_slot["start_date"], hero_slot["start_time"], hero_slot["end_time"], hero_slot["timezone"], hero_slot["status"]
    ) != ("2026-11-19", "10:00", "11:00", "America/New_York", "Available"):
        problems.append("[funding] hero executive review slot or timezone drifted")
    hero_legal = next((row for row in tables["staff_workload"] if row["notice_id"] == "FO-2026-117" and row["person_id"] == "LEGAL-01"), None)
    if hero_legal is None or (
        hero_legal["unavailable_from"], hero_legal["unavailable_through"], hero_legal["work_must_finish_by"]
    ) != ("2026-11-23", "2026-11-27", "2026-11-20"):
        problems.append("[funding] legal review availability/finish-by constraint drifted")
    for row in tables["submissions"]:
        if row["submission_state"] != "Not submitted" or row["submitted_at"]:
            problems.append(f"[funding] {row['notice_id']} must remain not submitted")

    registry_path = ROOT / "data" / "registry" / "funding_registry.yaml"
    ontology_path = ROOT / "data" / "ontology" / "funding_ontology.yaml"
    try:
        funding_registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        funding_ontology = yaml.safe_load(ontology_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        problems.append(f"[funding] registry or ontology cannot be loaded: {exc}")
    else:
        if funding_registry["resources"].get("fabric_dataset") != "award_iq_fabric_funding_ops":
            problems.append("[funding] Fabric funding dataset name drifted")
        registry_ids = {row["id"] for row in funding_registry["funding_opportunities"]}
        if registry_ids != set(opportunities):
            problems.append("[funding] canonical registry and operations notice IDs differ")
        ontology_tables = {
            entity.get("table")
            for entity in funding_ontology.get("entities", {}).values()
        }
        missing_ontology_tables = expected_names - ontology_tables
        if missing_ontology_tables:
            problems.append(f"[funding] ontology is missing tables: {sorted(missing_ontology_tables)}")

    with tempfile.TemporaryDirectory(prefix="award-iq-funding-") as temp_dir:
        generated = Path(temp_dir)
        generate_funding_tables(generated)
        for name in sorted(expected_names):
            generated_bytes = (generated / name).read_bytes()
            checked_in_bytes = (directory / name).read_bytes().replace(b"\r\n", b"\n")
            if b"\r\n" in generated_bytes:
                problems.append(f"[funding] {name} generator output does not use canonical LF endings")
            elif generated_bytes != checked_in_bytes:
                problems.append(f"[funding] {name} differs from deterministic generator output")

    return problems


def _source_url_allowed(url: str) -> bool:
    parsed = urlsplit(url.rstrip(".,);"))
    return parsed.scheme == "https" and parsed.hostname == "award-iq.example.invalid"


def validate_synthetic_provenance() -> list[str]:
    problems = []
    for directory in ("foundry_docs", "fabric/funding_ops", "work", "web"):
        for path in (ROOT / "data" / directory).rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".csv", ".json"}:
                continue
            for url in URL_RE.findall(path.read_text(encoding="utf-8")):
                if not _source_url_allowed(url):
                    problems.append(f"[provenance] {path.name}: disallowed source URL {url}")
    return problems


def scan() -> int:
    problems = validate_funding_ops() + validate_synthetic_provenance()
    if problems:
        print("\n".join(problems))
        return 1
    print("Award IQ funding data is consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(scan())
