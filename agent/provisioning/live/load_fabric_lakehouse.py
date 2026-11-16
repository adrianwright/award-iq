"""Load Award IQ synthetic funding CSVs into a Fabric Lakehouse as Delta tables.

1. Upload data/fabric/funding_ops/*.csv to OneLake Files/csv/ under the lakehouse.
2. Call the Fabric 'Load to Tables' API to convert each CSV -> Delta table.

Tokens are passed via env (from `az account get-access-token`) to avoid credential-chain issues:
  ONELAKE_TOKEN  (scope https://storage.azure.com/.default)
  FABRIC_TOKEN   (scope https://api.fabric.microsoft.com/.default)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from live_environment import required_environment

WS = required_environment("FABRIC_WS")
LH = required_environment("FABRIC_LH")
ONELAKE_TOKEN = required_environment("ONELAKE_TOKEN")
FABRIC_TOKEN = required_environment("FABRIC_TOKEN")
CSV_DIR = Path(os.environ.get("CSV_DIR", "data/fabric/funding_ops"))

ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
FABRIC = "https://api.fabric.microsoft.com/v1"

# Seed only an empty funding lakehouse. Existing tables and source files are never replaced.
TABLES = [
    "amendments", "approvals", "budget_lines", "community_metrics",
    "eligibility_criteria", "funding_opportunities", "match_sources", "partners",
    "people", "prior_proposals", "program_performance", "proposal_tasks",
    "scheduling_slots", "staff_workload", "submissions", "source_documents",
]


def _dfs(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{ONELAKE}/{WS}/{LH}/{path}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {ONELAKE_TOKEN}"
    return requests.request(method, url, headers=headers, timeout=60, **kwargs)


def upload_csv(name: str) -> None:
    local = CSV_DIR / f"{name}.csv"
    data = local.read_bytes()
    rel = f"Files/csv/{name}.csv"
    r = _dfs("PUT", f"{rel}?resource=file", headers={"If-None-Match": "*"})
    r.raise_for_status()
    r = _dfs("PATCH", f"{rel}?action=append&position=0", data=data,
             headers={"Content-Type": "application/octet-stream"})
    r.raise_for_status()
    r = _dfs("PATCH", f"{rel}?action=flush&position={len(data)}")
    r.raise_for_status()
    print(f"  uploaded {rel} ({len(data)} bytes)")


def load_table(name: str) -> None:
    url = f"{FABRIC}/workspaces/{WS}/lakehouses/{LH}/tables/{name}/load"
    body = {
        "relativePath": f"Files/csv/{name}.csv",
        "pathType": "File",
        "mode": "Append",
        "formatOptions": {"format": "Csv", "header": True, "delimiter": ","},
    }
    headers = {"Authorization": f"Bearer {FABRIC_TOKEN}", "Content-Type": "application/json"}
    r = requests.post(url, json=body, headers=headers, timeout=60)
    if r.status_code == 202:
        op = r.headers.get("Location")
        print(f"  load {name}: accepted, polling...")
        _poll(op)
    elif r.status_code in (200, 201):
        print(f"  load {name}: ok")
    else:
        print(f"  load {name}: HTTP {r.status_code} {r.text[:300]}")
        r.raise_for_status()


def _poll(op_url: str | None) -> None:
    if not op_url:
        raise RuntimeError("Fabric accepted the table load but returned no operation URL.")
    parsed = urlparse(op_url)
    if parsed.scheme != "https" or parsed.netloc != "api.fabric.microsoft.com":
        raise RuntimeError("Fabric returned an unexpected table-load operation URL.")
    headers = {"Authorization": f"Bearer {FABRIC_TOKEN}"}
    for _ in range(30):
        time.sleep(4)
        r = requests.get(op_url, headers=headers, timeout=60)
        r.raise_for_status()
        status = r.json().get("status") if r.headers.get("content-type", "").startswith("application/json") else None
        if status in ("Succeeded", "Completed"):
            print("    -> succeeded")
            return
        if status in ("Failed", "Cancelled"):
            raise RuntimeError(f"Fabric table load failed: {r.text[:300]}")
    raise TimeoutError("Fabric table load did not complete within 120 seconds.")


def main() -> None:
    headers = {"Authorization": f"Bearer {FABRIC_TOKEN}"}
    response = requests.get(
        f"{FABRIC}/workspaces/{WS}/lakehouses/{LH}/tables",
        headers=headers, timeout=60,
    )
    response.raise_for_status()
    existing = response.json()
    if existing.get("data") or existing.get("continuationToken"):
        raise RuntimeError("Refusing to seed a nonempty lakehouse. Existing tables were not modified.")
    for table in TABLES:
        if not (CSV_DIR / f"{table}.csv").is_file():
            raise FileNotFoundError(CSV_DIR / f"{table}.csv")
    print("Uploading CSVs to OneLake...")
    for t in TABLES:
        upload_csv(t)
    print("Loading Delta tables...")
    for t in TABLES:
        load_table(t)
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
