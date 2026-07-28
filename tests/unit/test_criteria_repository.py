"""Unit tests for the Criteria pattern and SQLServerRepository."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from scraper.storage.criteria import (
    AggregateFunction,
    Criteria,
    FilterOperator,
    OrderDirection,
    compile_criteria_to_sqlserver,
)
from scraper.storage.repository import SQLServerRepository


def test_compile_criteria_basic() -> None:
    criteria = Criteria.for_table("Telemetria_Tanque_N", schema="dbo").select_max(
        "timestamp", alias="last_val"
    )
    sql, params = compile_criteria_to_sqlserver(criteria)
    assert "SELECT MAX([timestamp]) AS [last_val] FROM [dbo].[Telemetria_Tanque_N]" in sql
    assert params == {}


def test_compile_criteria_where_and_order() -> None:
    criteria = (
        Criteria.for_table("Telemetria_Tanque_N")
        .where("nivel_tanque_pct", ">", 50.0)
        .where("presion_bar", "<=", 5.0)
        .order_by_desc("timestamp")
        .take(10)
    )
    sql, params = compile_criteria_to_sqlserver(criteria)
    assert "SELECT TOP (10) * FROM [dbo].[Telemetria_Tanque_N]" in sql
    assert "[nivel_tanque_pct] > :p_0" in sql
    assert "[presion_bar] <= :p_1" in sql
    assert "ORDER BY [timestamp] DESC" in sql
    assert params == {"p_0": 50.0, "p_1": 5.0}


def test_compile_criteria_in_operator() -> None:
    criteria = (
        Criteria.for_table("Cfg_Opciones")
        .where("codigo", FilterOperator.IN, ["OPT1", "OPT2"])
    )
    sql, params = compile_criteria_to_sqlserver(criteria)
    assert "[codigo] IN (:p_0_0, :p_0_1)" in sql
    assert params == {"p_0_0": "OPT1", "p_0_1": "OPT2"}


def test_parse_date_value_helpers() -> None:
    default_d = date(2024, 5, 1)
    assert SQLServerRepository._parse_date_value(date(2026, 7, 26), default_d) == date(2026, 7, 26)
    assert SQLServerRepository._parse_date_value("2026-07-26 00:00:00+02:00", default_d) == date(2026, 7, 26)
    assert SQLServerRepository._parse_date_value(None, default_d) == default_d
    assert SQLServerRepository._parse_date_value("invalid_date", default_d) == default_d


@pytest.mark.asyncio
async def test_repository_get_last_date_nonexistent_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that querying a nonexistent table returns default date 01/05/2024."""
    async def dummy_table_exists(*args: Any, **kwargs: Any) -> bool:
        return False

    repo = SQLServerRepository("mssql+pyodbc://mock")
    monkeypatch.setattr(repo, "table_exists", dummy_table_exists)

    last_dt = await repo.get_last_date("NonExistentTable", default_date=date(2024, 5, 1))
    assert last_dt == date(2024, 5, 1)


@pytest.mark.asyncio
async def test_repository_get_last_date_existing_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that querying an existing table with timestamps returns the parsed date."""
    async def dummy_table_exists(*args: Any, **kwargs: Any) -> bool:
        return True

    async def dummy_find_one(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return {"last_val": "2026-07-26 12:00:00+02:00"}

    repo = SQLServerRepository("mssql+pyodbc://mock")
    monkeypatch.setattr(repo, "table_exists", dummy_table_exists)
    monkeypatch.setattr(repo, "find_one", dummy_find_one)

    last_dt = await repo.get_last_date("Telemetria_Tanque_N", default_date=date(2024, 5, 1))
    assert last_dt == date(2026, 7, 26)
