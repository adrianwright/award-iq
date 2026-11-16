from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import MagicMock

import pyodbc
import pytest
from fastapi.testclient import TestClient

from app import funding, main
from app.config import Settings, SettingsConfigurationError, get_settings
from app.sources import fabric_funding
from app.sources.fabric_funding import FUNDING_TABLES, FundingDataUnavailable, read_funding_tables


def test_live_assessment_uses_fabric_rows_instead_of_local_financial_records(monkeypatch) -> None:
    settings = get_settings().model_copy(update={
        "USE_LIVE_FABRIC": True,
        "FABRIC_WORKSPACE_ID": "funding-workspace",
        "FABRIC_LAKEHOUSE_ID": "funding-lakehouse",
    })
    rows = {name: funding._read_rows(settings.DATA_DIR, name) for name in FUNDING_TABLES}
    confirmed = next(row for row in rows["match_sources"] if row["status"] == "Confirmed")
    confirmed["amount"] = str(int(confirmed["amount"]) + 100_000)
    monkeypatch.setattr(funding, "read_funding_tables", lambda _: rows)
    monkeypatch.setattr(funding, "_read_rows", lambda *_: pytest.fail("Local CSV fallback"))

    result = funding.assess_funding(settings, "FO-2026-117 confirmed match?")

    assert result.mode == "live"
    assert result.matchConfirmed == 1_900_000
    assert result.matchGap == 350_000
    assert all(
        "funding-lakehouse" in (item.url or "")
        for item in result.evidence if item.source.value == "fabric"
    )
    assert "not live M365" in next(
        item["retrieving"] for item in result.sourceMap if item["source"] == "work"
    )


def test_sql_reader_uses_token_tls_and_only_allowlisted_selects(monkeypatch) -> None:
    connect = MagicMock()
    credential = MagicMock()
    monkeypatch.setattr(fabric_funding, "AzureCliCredential", lambda **_: credential)
    monkeypatch.setattr(pyodbc, "connect", connect)
    credential.get_token.return_value.token = "test-token"
    cursor = connect.return_value.cursor.return_value
    cursor.description = [
        ("flag",), ("amount",), ("date",), ("optional",), ("start_time",), ("end_time",),
    ]
    cursor.fetchall.return_value = [(
        True, Decimal("1800000.00"), date(2026, 11, 16), None,
        datetime(2026, 11, 16, 10), time(11),
    )]

    tables = read_funding_tables(Settings(_env_file=None, FABRIC_SQL_SERVER="server", FABRIC_SQL_DATABASE="funding"))

    assert set(tables) == set(FUNDING_TABLES)
    assert tables["match_sources"][0] == {
        "flag": "true", "amount": "1800000", "date": "2026-11-16", "optional": "",
        "start_time": "10:00", "end_time": "11:00",
    }
    assert [call.args[0] for call in cursor.execute.call_args_list] == [
        f"SELECT TOP (10001) * FROM [dbo].[{table}]" for table in FUNDING_TABLES
    ]
    options = connect.call_args.kwargs
    assert "Encrypt=Yes;TrustServerCertificate=No" in connect.call_args.args[0]
    assert "ApplicationIntent=ReadOnly" in connect.call_args.args[0]
    assert options["attrs_before"][1256][4:] == "test-token".encode("utf-16-le")
    credential.get_token.assert_called_once_with("https://database.windows.net/.default")
    connect.return_value.close.assert_called_once()


def test_fabric_outage_fails_closed_for_json_and_stream(monkeypatch) -> None:
    def fail(*_, **__):
        raise FundingDataUnavailable("Fabric is paused; no fallback.")

    monkeypatch.setattr(main, "assess_funding", fail)
    client = TestClient(main.app)
    response = client.post("/api/funding/ask", json={"question": "match?"})
    assert response.status_code == 503
    response = client.post("/api/funding/ask/stream", json={"question": "match?"})
    assert "event: error" in response.text
    assert "event: final" not in response.text
    assert "no fallback" in response.text


def test_sql_failure_never_reads_packaged_funding_rows(monkeypatch) -> None:
    monkeypatch.setattr(fabric_funding, "AzureCliCredential", lambda **_: MagicMock())
    monkeypatch.setattr(pyodbc, "connect", MagicMock(side_effect=pyodbc.OperationalError("paused")))
    with pytest.raises(FundingDataUnavailable, match="No local fallback"):
        read_funding_tables(Settings(_env_file=None))


def test_connected_configuration_requires_funding_sql_coordinates() -> None:
    settings = Settings(
        _env_file=None, APP_ENVIRONMENT="production", USE_LIVE_FABRIC=True,
        AZURE_TENANT_ID="tenant", API_AUDIENCE="audience", AZURE_CLIENT_ID="identity",
        FABRIC_WORKSPACE_ID="workspace", FABRIC_LAKEHOUSE_ID="lakehouse",
        FABRIC_SQL_SERVER="server", FABRIC_SQL_DATABASE="funding",
    )
    settings.validate_runtime_configuration()
    with pytest.raises(SettingsConfigurationError, match="FABRIC_SQL_DATABASE"):
        settings.model_copy(update={"FABRIC_SQL_DATABASE": ""}).validate_runtime_configuration()
