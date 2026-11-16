from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

import provision_funding_knowledge as provisioner

DATA = Path(__file__).resolve().parents[3] / "data"


def test_index_contains_only_funding_documents_and_tracks_supersession():
    docs = provisioner.funding_documents(DATA)
    assert len(docs) == 12
    assert all(str(doc["filename"]).startswith("FO-") for doc in docs)
    amendment_1 = next(doc for doc in docs if doc["id"] == "DOC-FO117-AMD1")
    amendment_2 = next(doc for doc in docs if doc["id"] == "DOC-FO117-AMD2")
    assert amendment_1["valid_until"] == amendment_2["effective_from"]
    assert amendment_2["valid_until"] is None


def test_existing_index_is_not_overwritten_or_followed_by_document_writes(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        assert request.headers["If-None-Match"] == "*"
        return httpx.Response(412, json={"error": "Already exists"})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(provisioner.httpx, "Client", lambda **_: client)
    credential = MagicMock()
    credential.__enter__.return_value = credential
    credential.get_token.return_value.token = "test-token"
    monkeypatch.setattr(provisioner, "AzureCliCredential", lambda: credential)
    with pytest.raises(RuntimeError, match="412"):
        provisioner.provision(
            search_endpoint="https://award-test.search.windows.net",
            model_endpoint="https://award-test.openai.azure.com",
            model_deployment="test", model_name="test", data_dir=DATA,
        )
    assert len(requests) == 1
    assert requests[0].method == "PUT"
