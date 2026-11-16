"""Consistency validator for the synthetic data packages.

Checks retained source-project fixtures for identifier consistency, then validates the active
Award IQ funding tables, fixed scenario dates, calculation invariants, and deterministic generation.

Usage:  python tools/validate_consistency.py
Exit code 0 = consistent, 1 = problems found.
"""
from __future__ import annotations

import csv
import json
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
sys.path.insert(0, str(ROOT / "data" / "registry"))
from data.fabric.generate import generate as generate_fabric_tables  # noqa: E402
from data.fabric.funding_ops.generate import generate as generate_funding_tables  # noqa: E402
from loader import hero_patient, hero_trial, patient_ids, trial_ids  # noqa: E402

FABRIC_DIR = ROOT / "data" / "fabric"
DATA_DIRS = {
    "foundry": ROOT / "data" / "foundry_docs",
    "fabric": ROOT / "data" / "fabric",
    "work": ROOT / "data" / "work",
    "web": ROOT / "data" / "web",
}

# PT-#### patient tokens and NCT######## trial tokens (out-of-range NCT99xxxxxx form)
PT_RE = re.compile(r"\bPT-\d{4}\b")
NCT_RE = re.compile(r"\bNCT\d{8}\b")
URL_RE = re.compile(r'https?://[^\s"<>]+')

# The hero facts the whole proof-of-concept pivots on: they must never drift in the Fabric tables.
HERO_CRCL_SERIES = [("2026-05-20", "55"), ("2026-06-18", "48")]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_fabric_tables() -> list[str]:
    """Validate the generated Fabric entity tables: foreign keys resolve, hero rows are unchanged,
    every trial has at least one criterion, and there are no dangling references."""
    problems: list[str] = []
    try:
        tables = {
            name: _read_csv(FABRIC_DIR / name)
            for name in (
                "sites.csv", "people.csv", "patient_registry.csv", "biomarkers.csv", "labs.csv",
                "treatment_history.csv", "comorbidities.csv", "adverse_events.csv",
                "recist_assessments.csv", "consent.csv", "trials.csv", "trial_criteria.csv",
                "amendments.csv", "trial_enrollment.csv", "coordinator_workload.csv",
                "scheduling_slots.csv",
            )
        }
    except FileNotFoundError as exc:
        return [f"[fabric] missing generated table: {exc.filename} (run python data/fabric/generate.py)"]

    patient_ids_set = {r["patient_id"] for r in tables["patient_registry.csv"]}
    trial_ids_set = {r["trial_id"] for r in tables["trials.csv"]}
    site_ids_set = {r["site_id"] for r in tables["sites.csv"]}
    person_ids_set = {r["person_id"] for r in tables["people.csv"]}
    coordinator_ids_set = {r["coordinator_id"] for r in tables["coordinator_workload.csv"]}
    criterion_ids_set = {r["criterion_id"] for r in tables["trial_criteria.csv"]}

    # Foreign keys that must resolve.
    for table in ("labs.csv", "biomarkers.csv", "treatment_history.csv", "comorbidities.csv",
                  "adverse_events.csv", "recist_assessments.csv", "consent.csv", "trial_enrollment.csv"):
        for r in tables[table]:
            if r["patient_id"] not in patient_ids_set:
                problems.append(f"[fabric] {table}: dangling patient_id {r['patient_id']}")
    for r in tables["patient_registry.csv"]:
        if r["treating_oncologist_id"] not in person_ids_set:
            problems.append(f"[fabric] patient_registry.csv: dangling treating_oncologist_id {r['treating_oncologist_id']}")
        if r["coordinator_id"] not in coordinator_ids_set:
            problems.append(f"[fabric] patient_registry.csv: dangling coordinator_id {r['coordinator_id']}")
    for r in tables["people.csv"]:
        if r["site_id"] not in site_ids_set:
            problems.append(f"[fabric] people.csv: dangling site_id {r['site_id']}")
    for r in tables["trials.csv"]:
        if r["site_id"] not in site_ids_set:
            problems.append(f"[fabric] trials.csv: dangling site_id {r['site_id']}")
    for table in ("trial_criteria.csv", "amendments.csv", "trial_enrollment.csv", "consent.csv"):
        for r in tables[table]:
            if r["trial_id"] not in trial_ids_set:
                problems.append(f"[fabric] {table}: dangling trial_id {r['trial_id']}")
    for r in tables["amendments.csv"]:
        if r["modifies_criterion_id"] not in criterion_ids_set:
            problems.append(f"[fabric] amendments.csv: dangling modifies_criterion_id {r['modifies_criterion_id']}")
    for r in tables["scheduling_slots.csv"]:
        if r["site_id"] not in site_ids_set:
            problems.append(f"[fabric] scheduling_slots.csv: dangling site_id {r['site_id']}")
        if r["assigned_patient_id"] and r["assigned_patient_id"] not in patient_ids_set:
            problems.append(f"[fabric] scheduling_slots.csv: dangling assigned_patient_id {r['assigned_patient_id']}")

    # Every trial must have at least one criterion.
    trials_with_criteria = {r["trial_id"] for r in tables["trial_criteria.csv"]}
    for tid in trial_ids_set:
        if tid not in trials_with_criteria:
            problems.append(f"[fabric] trial {tid} has no criteria")

    # Hero rows must be unchanged.
    hero_crcl = sorted(
        ((r["lab_date"], r["value"]) for r in tables["labs.csv"]
         if r["patient_id"] == "PT-1042" and r["lab_type"] == "CrCl_CKD-EPI"),
        key=lambda item: item[0],
    )
    if hero_crcl != HERO_CRCL_SERIES:
        problems.append(f"[fabric] hero PT-1042 CrCl series changed: {hero_crcl} (expected {HERO_CRCL_SERIES})")
    hero_trial_row = next((r for r in tables["trials.csv"] if r["trial_id"] == "NCT99004324"), None)
    if hero_trial_row is None:
        problems.append("[fabric] hero trial NCT99004324 missing from trials.csv")
    else:
        if hero_trial_row["crcl_min"] != "50":
            problems.append(f"[fabric] hero trial crcl_min changed: {hero_trial_row['crcl_min']} (expected 50)")
        if hero_trial_row["biomarker_required"] != "EGFR exon 20 insertion":
            problems.append(f"[fabric] hero trial biomarker_required changed: {hero_trial_row['biomarker_required']}")
        if hero_trial_row["short_title"] != "EGFR exon 20 NSCLC":
            problems.append(f"[fabric] hero trial short_title changed: {hero_trial_row['short_title']}")

    return problems


def validate_generated_fabric_output() -> list[str]:
    """Regenerate tables outside the repository and compare every CSV byte-for-byte."""
    problems: list[str] = []
    expected_paths = sorted(FABRIC_DIR.glob("*.csv"))
    with tempfile.TemporaryDirectory(prefix="amciq-fabric-") as temp_dir:
        generated_dir = Path(temp_dir)
        generate_fabric_tables(generated_dir)
        generated_paths = sorted(generated_dir.glob("*.csv"))
        if [path.name for path in generated_paths] != [path.name for path in expected_paths]:
            return ["[fabric] generated CSV file set differs from the checked-in file set"]
        for expected, generated in zip(expected_paths, generated_paths, strict=True):
            expected_bytes = expected.read_bytes().replace(b"\r\n", b"\n")
            generated_bytes = generated.read_bytes()
            if b"\r\n" in generated_bytes:
                problems.append(
                    f"[fabric] {generated.name} generator output does not use canonical LF endings"
                )
            elif expected_bytes != generated_bytes:
                problems.append(
                    f"[fabric] {expected.name} differs from deterministic generator output"
                )
    return problems


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
            if (generated / name).read_bytes() != (directory / name).read_bytes():
                problems.append(f"[funding] {name} differs from deterministic generator output")

    return problems


def _source_url_allowed(url: str, known_nct: set[str]) -> bool:
    parsed = urlsplit(url.rstrip(".,);"))
    if parsed.scheme != "https":
        return False
    if parsed.hostname in {"amciq.example.invalid", "award-iq.example.invalid"}:
        return True
    return (
        parsed.hostname == "clinicaltrials.gov"
        and parsed.path.startswith("/study/")
        and parsed.path.removeprefix("/study/") in known_nct
    )


def validate_synthetic_provenance(known_nct: set[str]) -> list[str]:
    """Keep fictional identifiers and source metadata visibly synthetic and non-resolving."""
    problems: list[str] = []
    for trial_id in known_nct:
        if not re.fullmatch(r"NCT99\d{6}", trial_id):
            problems.append(
                f"[registry] trial {trial_id} is outside the documented NCT99 synthetic range"
            )

    for layer, directory in DATA_DIRS.items():
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for url in URL_RE.findall(text):
                if _source_url_allowed(url, known_nct):
                    continue
                parsed = urlsplit(url.rstrip(".,);"))
                problems.append(
                    f"[{layer}] {path.name}: disallowed source URL "
                    f"{parsed.scheme}://{parsed.hostname}"
                )

    manifest_path = DATA_DIRS["web"] / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"[web] cannot parse manifest.json: {exc}")
    else:
        seen_files: set[str] = set()
        for entry in manifest:
            entry_file = str(entry.get("file", ""))
            if (
                not entry_file
                or Path(entry_file).is_absolute()
                or ".." in Path(entry_file).parts
            ):
                problems.append(f"[web] manifest has unsafe file path {entry_file!r}")
                continue
            if entry_file in seen_files:
                problems.append(f"[web] manifest contains duplicate file {entry_file}")
            seen_files.add(entry_file)
            if not (DATA_DIRS["web"] / entry_file).is_file():
                problems.append(f"[web] manifest target does not exist: {entry_file}")
            if entry.get("synthetic") is not True:
                problems.append(
                    f"[web] manifest entry {entry_file or '<unknown>'} is not marked synthetic"
                )
            if entry_file.endswith(".json") and (DATA_DIRS["web"] / entry_file).is_file():
                try:
                    record = json.loads(
                        (DATA_DIRS["web"] / entry_file).read_text(encoding="utf-8")
                    )
                except json.JSONDecodeError as exc:
                    problems.append(f"[web] cannot parse {entry_file}: {exc}")
                else:
                    if isinstance(record, dict) and record.get("synthetic") is not True:
                        problems.append(f"[web] record {entry_file} is not marked synthetic")
    return problems


def scan() -> int:
    known_pt = patient_ids()
    known_nct = trial_ids()
    hero_pt = hero_patient()["id"]
    hero_nct = hero_trial()["id"]

    problems: list[str] = []
    layer_has_hero_pt: dict[str, bool] = {k: False for k in DATA_DIRS}
    layer_has_hero_nct: dict[str, bool] = {k: False for k in DATA_DIRS}
    file_count = 0

    # The web layer is external content (trial registry, labels, guidelines, evidence);
    # it references the hero *trial* but not internal patient IDs, by design.
    patient_required_layers = {"foundry", "fabric", "work"}
    trial_required_layers = set(DATA_DIRS)

    for layer, d in DATA_DIRS.items():
        if not d.exists():
            problems.append(f"[{layer}] directory missing: {d}")
            continue
        files = [
            f
            for f in d.rglob("*")
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc"
        ]
        if not files:
            problems.append(f"[{layer}] no files generated in {d}")
        for f in files:
            file_count += 1
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:  # noqa: BLE001
                problems.append(f"[{layer}] cannot read {f.name}: {e}")
                continue
            for pt in set(PT_RE.findall(text)):
                if pt not in known_pt:
                    problems.append(f"[{layer}] {f.name}: unknown patient id {pt}")
            for nct in set(NCT_RE.findall(text)):
                if nct not in known_nct:
                    problems.append(f"[{layer}] {f.name}: unknown trial id {nct}")
            if hero_pt in text:
                layer_has_hero_pt[layer] = True
            if hero_nct in text:
                layer_has_hero_nct[layer] = True

    for layer in DATA_DIRS:
        if layer in patient_required_layers and not layer_has_hero_pt[layer]:
            problems.append(f"[{layer}] hero patient {hero_pt} not referenced")
        if layer in trial_required_layers and not layer_has_hero_nct[layer]:
            problems.append(f"[{layer}] hero trial {hero_nct} not referenced")

    print(f"Scanned {file_count} files across {len(DATA_DIRS)} layers.")
    print("Validated retained legacy clinical fixture identifiers.")

    fabric_problems = validate_fabric_tables()
    problems.extend(fabric_problems)
    print(f"Validated retained clinical Fabric tables: {'OK' if not fabric_problems else f'{len(fabric_problems)} problem(s)'}.")

    generation_problems = validate_generated_fabric_output()
    problems.extend(generation_problems)
    print(
        "Validated retained clinical Fabric regeneration: "
        f"{'OK' if not generation_problems else f'{len(generation_problems)} problem(s)'}."
    )

    funding_problems = validate_funding_ops()
    problems.extend(funding_problems)
    print(
        "Validated Award IQ funding tables: "
        f"{'OK' if not funding_problems else f'{len(funding_problems)} problem(s)'}."
    )

    provenance_problems = validate_synthetic_provenance(known_nct)
    problems.extend(provenance_problems)
    print(
        "Validated synthetic identifiers and source metadata: "
        f"{'OK' if not provenance_problems else f'{len(provenance_problems)} problem(s)'}."
    )

    if problems:
        print(f"\nFAIL, {len(problems)} consistency problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        "\nOK, retained legacy fixtures are consistent and Award IQ funding tables, dates, "
        "calculations, and deterministic generation validate."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(scan())
