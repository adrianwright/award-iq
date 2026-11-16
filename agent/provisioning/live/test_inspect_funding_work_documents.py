from argparse import Namespace

import httpx
import pytest

import inspect_funding_work_documents as inspection
from inspect_funding_work_documents import FILENAMES, children, document_identities, document_map


def test_listing_follows_exact_graph_pagination():
    next_link = "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=opaque"
    calls = []

    def handle(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(200, json={"value": [{"id": "one"}], "@odata.nextLink": next_link})
        assert str(request.url) == next_link
        return httpx.Response(200, json={"value": [{"id": "two"}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert children(client, "/me/drive/root/children") == [{"id": "one"}, {"id": "two"}]


@pytest.mark.parametrize("status", [401, 403, 404, 429])
def test_listing_stops_on_failure_without_retry_or_alternate_path(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": "denied"}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError, match=f"HTTP {status}"):
            children(client, "/me/drive/root/children")
    assert len(calls) == 1


def test_pagination_cannot_forward_token_to_another_host():
    def handle(request):
        return httpx.Response(200, json={
            "value": [],
            "@odata.nextLink": "https://other.example/collect",
        })

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError, match="unexpected"):
            children(client, "/me/drive/root/children")


def test_document_map_requires_all_exact_files_and_safe_canonical_links():
    items = [
        {"name": name, "webUrl": f"https://demo.sharepoint.com/Documents/{name}"}
        for name in FILENAMES
    ]
    assert len(document_map(items)) == 6
    with pytest.raises(RuntimeError, match="found 2"):
        document_map(items + [items[0]])
    items[0] = {**items[0], "webUrl": items[0]["webUrl"] + "?token=secret"}
    with pytest.raises(RuntimeError, match="safe canonical"):
        document_map(items)


def test_document_identities_bind_exact_returned_drive_items_to_verified_urls():
    item = {
        "id": "opaque-item", "webUrl": "https://demo.sharepoint.com/Documents/demo.md",
        "parentReference": {"driveId": "opaque-drive"},
    }
    urls = {"DOC": item["webUrl"]}
    assert document_identities([item], urls) == {
        "DOC": {"webUrl": item["webUrl"], "driveId": "opaque-drive", "itemId": "opaque-item"},
    }
    with pytest.raises(RuntimeError, match="Missing drive/item"):
        document_identities([{**item, "parentReference": {}}], urls)
    with pytest.raises(RuntimeError, match="same drive item"):
        document_identities([item], {**urls, "OTHER": item["webUrl"]})


@pytest.mark.parametrize("account_id", ["expected-user", "different-user"])
def test_cached_sign_in_validates_account_without_requiring_new_id_token(
    monkeypatch, tmp_path, account_id, capsys,
):
    class App:
        def get_accounts(self, **kwargs):
            return [{"realm": "tenant", "local_account_id": account_id}]

        def acquire_token_silent(self, scopes, account):
            return {"access_token": "private-token", "token_source": "cache"}

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(inspection, "build_encrypted_persistence", lambda _: object())
    monkeypatch.setattr(inspection, "PersistedTokenCache", lambda _: object())
    monkeypatch.setattr(inspection.msal, "PublicClientApplication", lambda *a, **k: App())
    args = Namespace(
        client_id="client", tenant_id="tenant", username="operator",
        user_object_id="expected-user",
    )
    if account_id == "expected-user":
        assert inspection.acquire_token(args) == "private-token"
    else:
        with pytest.raises(RuntimeError, match="Cached sign-in identity"):
            inspection.acquire_token(args)
    assert "private-token" not in capsys.readouterr().out
