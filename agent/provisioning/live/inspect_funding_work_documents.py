"""Read Award IQ OneDrive document metadata using an explicitly consented setup client.

No Azure CLI file token, M365 writes, plaintext token cache or automatic scope escalation.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
import msal
from msal_extensions import PersistedTokenCache, build_encrypted_persistence

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["https://graph.microsoft.com/Files.Read"]
FILENAMES = {
    "FO-2026-117_review_minutes_2026-11-05.md",
    "FO-2026-117_readiness_tracker_v2.md",
    "FO-2026-117_match_funding_memo_v2.md",
    "FO-2026-117_proposal_huddle_2026-11-09.md",
    "FO-2026-204_readiness_v1.md",
    "FO-2026-330_readiness_v1.md",
}


def acquire_token(args: argparse.Namespace) -> str:
    cache_path = (
        Path(os.environ["LOCALAPPDATA"]) / "Award IQ" / "msal" / f"{args.client_id}.bin"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = PersistedTokenCache(build_encrypted_persistence(str(cache_path)))
    app = msal.PublicClientApplication(
        args.client_id,
        authority=f"https://login.microsoftonline.com/{args.tenant_id}",
        token_cache=cache,
    )
    accounts = app.get_accounts(username=args.username)
    if len(accounts) > 1:
        raise RuntimeError("Multiple cached accounts match; resolve the ambiguity before continuing.")
    if accounts and (
        accounts[0].get("realm") != args.tenant_id
        or accounts[0].get("local_account_id") != args.user_object_id
    ):
        raise RuntimeError("Cached sign-in identity does not match the explicitly selected Azure operator.")
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    from_cache = bool(result and "access_token" in result)
    if result and "access_token" not in result:
        raise RuntimeError(f"Cached sign-in failed: {result.get('error_description', result.get('error'))}")
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Cannot start sign-in: {flow.get('error_description', flow.get('error'))}")
        print(flow["message"], flush=True)
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Sign-in failed: {result.get('error_description', result.get('error'))}")
    if not from_cache:
        claims = result.get("id_token_claims", {})
        if claims.get("tid") != args.tenant_id or claims.get("oid") != args.user_object_id:
            raise RuntimeError("Sign-in identity does not match the explicitly selected Azure operator.")
    print("DELEGATED_READ_ONLY_SIGN_IN_OK", flush=True)
    return result["access_token"]


def children(client: httpx.Client, path: str) -> list[dict]:
    url = f"{GRAPH}{path}?$select=id,name,webUrl,folder,parentReference&$top=200"
    items: list[dict] = []
    seen: set[str] = set()
    while url:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "graph.microsoft.com"
            or not parsed.path.startswith("/v1.0/me/drive/")
            or url in seen
        ):
            raise RuntimeError("Graph returned an unexpected or repeated pagination link.")
        seen.add(url)
        response = client.get(url)
        if not response.is_success:
            raise RuntimeError(
                f"OneDrive metadata read failed with HTTP {response.status_code}: "
                f"{response.text[:600]}. Stopping without another access strategy."
            )
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("value"), list):
            raise RuntimeError("Graph returned an invalid folder listing.")
        if any(not isinstance(item, dict) for item in body["value"]):
            raise RuntimeError("Graph returned malformed file metadata.")
        items.extend(body["value"])
        url = body.get("@odata.nextLink", "")
        if not isinstance(url, str):
            raise RuntimeError("Graph returned an invalid pagination link.")
    return items


def document_map(items: list[dict]) -> dict[str, str]:
    registry = Path(__file__).resolve().parents[3] / "data" / "fabric" / "funding_ops" / "source_documents.csv"
    with registry.open(encoding="utf-8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["filename"] in FILENAMES]
    matches: dict[str, str] = {}
    for row in rows:
        found = [item for item in items if item.get("name") == row["filename"] and "folder" not in item]
        if len(found) != 1:
            raise RuntimeError(f"Expected exactly one {row['filename']}; found {len(found)}.")
        url = found[0].get("webUrl")
        parsed = urlparse(url) if isinstance(url, str) else None
        if (
            parsed is None or parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".sharepoint.com") or parsed.username
            or parsed.password or parsed.query or parsed.fragment
        ):
            raise RuntimeError(f"Document has no safe canonical SharePoint URL: {row['filename']}")
        matches[row["document_id"]] = url
    if len(matches) != len(FILENAMES):
        raise RuntimeError("The funding registry is missing one or more expected documents.")
    return matches


def document_identities(items: list[dict], urls: dict[str, str]) -> dict[str, dict[str, str]]:
    identities: dict[str, dict[str, str]] = {}
    seen: set[tuple[str, str]] = set()
    for document_id, url in urls.items():
        found = [item for item in items if item.get("webUrl") == url and "folder" not in item]
        if len(found) != 1:
            raise RuntimeError(f"Expected one verified metadata record for {document_id}.")
        parent = found[0].get("parentReference")
        drive_id = parent.get("driveId") if isinstance(parent, dict) else None
        item_id = found[0].get("id")
        if not isinstance(drive_id, str) or not drive_id or not isinstance(item_id, str) or not item_id:
            raise RuntimeError(f"Missing drive/item identity for {document_id}.")
        if (drive_id, item_id) in seen:
            raise RuntimeError("Two configured documents resolve to the same drive item.")
        seen.add((drive_id, item_id))
        identities[document_id] = {"webUrl": url, "driveId": drive_id, "itemId": item_id}
    return identities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("tenant-id", "client-id", "username", "user-object-id", "output"):
        parser.add_argument(f"--{field}", required=True)
    parser.add_argument("--folder-id", help="Actual returned folder ID; never a sharing token.")
    parser.add_argument("--identity-output", help="Optional verified drive/item identity map output.")
    args = parser.parse_args()
    token = acquire_token(args)
    with httpx.Client(
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=30, follow_redirects=False,
    ) as client:
        if args.folder_id:
            folder_id = args.folder_id
        else:
            root = children(client, "/me/drive/root/children")
            folders = [
                item for item in root if "folder" in item
                and "award" in str(item.get("name", "")).casefold()
            ]
            print(json.dumps({"awardFolderCandidates": folders}, indent=2), flush=True)
            print("Folder discovery only. Confirm the intended folder before reading its contents.")
            return
        items = children(client, f"/me/drive/items/{quote(folder_id, safe='')}/children")
    urls = document_map(items)
    identities = document_identities(items, urls) if args.identity_output else None
    output = Path(args.output)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(urls, stream, indent=2)
    if args.identity_output:
        with Path(args.identity_output).open("x", encoding="utf-8") as stream:
            json.dump(identities, stream, indent=2)
    print(json.dumps({"verifiedDocumentCount": len(urls), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
