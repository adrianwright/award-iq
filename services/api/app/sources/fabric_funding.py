from __future__ import annotations

import logging
import struct
from contextlib import closing
from datetime import date, datetime, time
from decimal import Decimal

from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential, ManagedIdentityCredential

from app.config import Settings

logger = logging.getLogger(__name__)

FUNDING_TABLES = (
    "funding_opportunities", "amendments", "eligibility_criteria", "budget_lines",
    "match_sources", "partners", "people", "prior_proposals", "program_performance",
    "community_metrics", "staff_workload", "scheduling_slots", "approvals",
    "submissions", "proposal_tasks", "source_documents",
)
MAX_TABLE_ROWS = 10_000


class FundingDataUnavailable(RuntimeError):
    """An authoritative funding source or its grounded synthesis is unavailable."""


def _text(value: object, column: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if column in {"start_time", "end_time"} and isinstance(value, (datetime, time)):
        return value.strftime("%H:%M")
    if isinstance(value, datetime):
        if value.time().isoformat() == "00:00:00":
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f") if value % 1 else str(int(value))
    return str(value)


def read_funding_tables(settings: Settings) -> dict[str, list[dict[str, str]]]:
    """Read only allowlisted tables; never substitute packaged CSV data on failure."""
    try:
        import pyodbc
    except ImportError as exc:
        logger.exception("The live Fabric SQL driver could not be loaded")
        raise FundingDataUnavailable(
            "Live Fabric requires pyodbc and Microsoft ODBC Driver 18 for SQL Server."
        ) from exc
    credential = (
        ManagedIdentityCredential(client_id=settings.AZURE_CLIENT_ID)
        if settings.AZURE_CLIENT_ID
        else AzureCliCredential(tenant_id=settings.AZURE_TENANT_ID)
    )
    try:
        with credential:
            token = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
            # SQL_COPT_SS_ACCESS_TOKEN expects a byte length followed by the UTF-16-LE token.
            access_token = struct.pack("<I", len(token)) + token
            with closing(pyodbc.connect(
                "Driver={ODBC Driver 18 for SQL Server};"
                f"Server={settings.FABRIC_SQL_SERVER};Database={settings.FABRIC_SQL_DATABASE};"
                "Encrypt=Yes;TrustServerCertificate=No;ApplicationIntent=ReadOnly;"
                "APP=Award IQ funding reader;",
                attrs_before={1256: access_token},
                autocommit=True,
                timeout=30,
            )) as connection:
                connection.timeout = 60
                tables = {}
                with closing(connection.cursor()) as cursor:
                    for table in FUNDING_TABLES:
                        cursor.execute(f"SELECT TOP ({MAX_TABLE_ROWS + 1}) * FROM [dbo].[{table}]")
                        columns = [column[0] for column in cursor.description]
                        rows = cursor.fetchall()
                        if len(rows) > MAX_TABLE_ROWS:
                            raise FundingDataUnavailable(
                                f"Fabric table {table} exceeds the supported {MAX_TABLE_ROWS} rows."
                            )
                        tables[table] = [
                            {name: _text(value, name) for name, value in zip(columns, row, strict=True)}
                            for row in rows
                        ]
                if not tables["funding_opportunities"]:
                    raise FundingDataUnavailable("Fabric has no funding opportunities.")
                return tables
    except (pyodbc.Error, OSError, AzureError, TimeoutError) as exc:
        logger.exception("Live Fabric funding-table read failed")
        raise FundingDataUnavailable(
            "Live Fabric funding data is unavailable. Check capacity state, SQL endpoint, "
            "and the application's lakehouse permissions. No local fallback was used."
        ) from exc
