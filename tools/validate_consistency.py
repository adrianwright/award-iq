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
    """Validate Award IQ funding table coverage, arithmetic, dates, and deterministic generation."""
    problems: list[str] = []
    directory = FABRIC_DIR / "funding_ops"
    expected_names = {
        "amendments.csv", "approvals.csv", "budget_lines.csv", "community_metrics.csv",
        "eligibility_criteria.csv", "funding_opportunities.csv", "match_sources.csv",
        "partners.csv", "people.csv", "prior_proposals.csv", "program_performance.csv",
        "scheduling_slots.csv", "staff_workload.csv", "submissions.csv", "proposal_tasks.csv",
    }
    actual_names = {path.name for path in directory.glob("*.csv")}
    if actual_names != expected_names:
        problems.append(
            f"[funding] table set differs: missing={sorted(expected_names - actual_names)}, "
            f"unexpected={sorted(actual_names - expected_names)}"
        )
        return problems

    tables = {name[:-4]: _read_csv(directory / name) for name in sorted(expected_names)}
    notice = next((row for row in tables["funding_opportunities"] if row["notice_id"] == "FO-2026-117"), None)
    if notice is None:
        return ["[funding] FO-2026-117 is missing from funding_opportunities"]
    as_of = date.fromisoformat(notice["as_of_date"])
    deadline = date.fromisoformat(notice["deadline"])
    if as_of.isoformat() != "2026-11-16" or deadline.isoformat() != "2026-12-16":
        problems.append("[funding] pinned scenario date or application deadline changed")
    if (deadline - as_of).days != 30:
        problems.append("[funding] scenario deadline is not exactly 30 days after its as-of date")

    amendments = [
        row for row in tables["amendments"]
        if row["notice_id"] == notice["notice_id"] and date.fromisoformat(row["effective_date"]) <= as_of
    ]
    latest = max(amendments, key=lambda row: (row["effective_date"], int(row["amendment"]))) if amendments else None
    if latest is None or latest["amendment"] != "2" or latest["status"] != "Current":
        problems.append("[funding] latest effective amendment is not current Amendment 2")
    else:
        required = round(int(notice["total_project_cost"]) * float(latest["match_rate"]))
        if latest["match_rate"] != "0.25" or latest["regional_partner_required"].casefold() != "true":
            problems.append("[funding] Amendment 2 must require 25% match and a regional partner")
        budget = next(
            (row for row in tables["budget_lines"] if row["notice_id"] == notice["notice_id"] and row["classification"] == "Required match"),
            None,
        )
        if budget is None or int(budget["amount"]) != required:
            problems.append("[funding] required match does not match the current amendment calculation")

    sources = [row for row in tables["match_sources"] if row["notice_id"] == notice["notice_id"]]
    confirmed = sum(int(row["amount"]) for row in sources if row["status"].casefold() == "confirmed")
    proposed = sum(int(row["amount"]) for row in sources if row["status"].casefold() == "proposed")
    if confirmed != 1_800_000 or proposed != 450_000:
        problems.append(
            f"[funding] expected $1,800,000 confirmed and $450,000 proposed; got {confirmed} and {proposed}"
        )

    people_ids = {row["person_id"] for row in tables["people"]}
    for task in tables["proposal_tasks"]:
        if task["owner_id"] not in people_ids:
            problems.append(f"[funding] {task['task_id']} has unknown owner {task['owner_id']}")
    task_ids = {row["task_id"] for row in tables["proposal_tasks"]}
    if task_ids != {"TASK-117-MATCH", "TASK-117-PARTNER"}:
        problems.append("[funding] required match and partner tasks are missing")
    else:
        expected_tasks = {
            "TASK-117-MATCH": ("FIN-02", "2026-11-18"),
            "TASK-117-PARTNER": ("PM-01", "2026-11-20"),
        }
        for task in tables["proposal_tasks"]:
            if (task["owner_id"], task["due_date"]) != expected_tasks[task["task_id"]]:
                problems.append(f"[funding] {task['task_id']} owner or due date drifted")

    review = next(
        (row for row in tables["approvals"] if row["notice_id"] == notice["notice_id"]),
        None,
    )
    if review is None or review["decision"] != "Pursue - pending" or "not an approval" not in review["record_type"].casefold():
        problems.append("[funding] pending pursuit record or its non-approval boundary is missing")
    partner = next(
        (row for row in tables["partners"] if row["notice_id"] == notice["notice_id"]),
        None,
    )
    if partner is None or partner["current_commitment"] != "Not received":
        problems.append("[funding] current partner commitment must remain unresolved")
    slot = next(
        (row for row in tables["scheduling_slots"] if row["notice_id"] == notice["notice_id"]),
        None,
    )
    if slot is None or (
        slot["date"], slot["start_time"], slot["end_time"], slot["timezone"]
    ) != ("2026-11-19", "10:00", "11:00", "America/Los_Angeles (PST, UTC-08:00)"):
        problems.append("[funding] executive-review window or explicit timezone drifted")
    legal = next(
        (row for row in tables["staff_workload"] if row["notice_id"] == notice["notice_id"]),
        None,
    )
    if legal is None or (
        legal["person_id"], legal["unavailable_from"], legal["unavailable_through"],
        legal["work_must_finish_by"],
    ) != ("LEGAL-01", "2026-11-23", "2026-11-27", "2026-11-20"):
        problems.append("[funding] legal availability deadline drifted")
    submission = next(
        (row for row in tables["submissions"] if row["notice_id"] == notice["notice_id"]),
        None,
    )
    if submission is None or submission["status"] != "Not submitted" or submission["submitted_at"]:
        problems.append("[funding] application must remain unsubmitted")

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
        if funding_registry["funding_opportunities"][0]["id"] != notice["notice_id"]:
            problems.append("[funding] canonical registry and operations table notice IDs differ")
        ontology_tables = {
            entity.get("table")
            for entity in funding_ontology.get("entities", {}).values()
        }
        missing_ontology_tables = {
            name.removesuffix(".csv") + ".csv" for name in expected_names
        } - ontology_tables
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
    print(f"Retained legacy clinical patient IDs: {sorted(known_pt)}")
    print(f"Retained legacy clinical trial IDs:   {sorted(known_nct)}")

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
