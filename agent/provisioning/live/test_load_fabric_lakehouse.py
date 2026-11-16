from __future__ import annotations

import os
from unittest.mock import Mock

import pytest

for name in ("FABRIC_WS", "FABRIC_LH", "ONELAKE_TOKEN", "FABRIC_TOKEN"):
    os.environ.setdefault(name, "test-only")

import load_fabric_lakehouse as loader


def test_seed_refuses_existing_tables_before_writing_files(monkeypatch) -> None:
    response = Mock()
    response.json.return_value = {"data": [{"name": "other_demo_table"}]}
    monkeypatch.setattr(loader.requests, "get", lambda *_, **__: response)
    upload = Mock()
    monkeypatch.setattr(loader, "upload_csv", upload)

    with pytest.raises(RuntimeError, match="nonempty lakehouse"):
        loader.main()
    upload.assert_not_called()


def test_table_load_failure_is_not_reported_as_success(monkeypatch) -> None:
    response = Mock()
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {"status": "Failed"}
    response.text = "Seed load failed"
    monkeypatch.setattr(loader.requests, "get", lambda *_, **__: response)
    monkeypatch.setattr(loader.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="table load failed"):
        loader._poll("https://api.fabric.microsoft.com/v1/operations/test")


def test_csv_upload_never_replaces_existing_files(tmp_path, monkeypatch) -> None:
    (tmp_path / "people.csv").write_text("person_id\nPM-01\n", encoding="utf-8")
    monkeypatch.setattr(loader, "CSV_DIR", tmp_path)
    dfs = Mock()
    monkeypatch.setattr(loader, "_dfs", dfs)

    loader.upload_csv("people")

    assert dfs.call_args_list[0].kwargs["headers"] == {"If-None-Match": "*"}
