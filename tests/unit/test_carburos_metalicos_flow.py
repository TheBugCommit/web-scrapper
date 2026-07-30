"""Regression test for the carburos_metalicos date bug (code_review.md, critical #1):

`run_flow()` must resume scraping from `get_last_date()` — the function existed
but was never called; `run_flow()` used a hardcoded 92-day window instead,
risking silent data loss if the job didn't run for more than 92 days.

Heavily mocks the builder/engine chain so this stays a fast, offline unit test
(no browser, no real database, no network).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_run_flow_resumes_from_get_last_date(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import portals.carburos_metalicos.flow as flow

    # A date far outside any hardcoded fixed window — if run_flow() ever
    # regresses back to a hardcoded window, this value will not be used and
    # the assertion on get_last_date's call args (or its being awaited at
    # all) will fail.
    sentinel_start = date(2020, 1, 1)
    get_last_date_mock = AsyncMock(return_value=sentinel_start)
    monkeypatch.setattr(flow, "get_last_date", get_last_date_mock)

    fake_portal = MagicMock()
    fake_portal.name = "Carburos Metalicos"
    fake_portal.portal_url = "https://example.com"
    fake_portal.extra = {}

    fake_builder = MagicMock()
    fake_builder.with_download_dir.return_value = fake_builder
    fake_builder.with_interaction.return_value = fake_builder
    fake_builder.with_extractor.return_value = fake_builder
    fake_builder.with_storage.return_value = fake_builder
    fake_builder.build.return_value = MagicMock()
    fake_portal.get_builder.return_value = fake_builder
    fake_portal.get_storage.return_value = MagicMock()

    fake_registry = MagicMock()
    fake_registry.get.return_value = fake_portal
    monkeypatch.setattr(flow.PortalRegistry, "load", MagicMock(return_value=fake_registry))

    monkeypatch.setattr(flow, "DOWNLOAD_DIR", tmp_path / "downloads")
    monkeypatch.setattr(flow, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setenv("SCRAPER_DB_CONNECTION_STRING", "mssql+pyodbc://dummy")

    engine_instance = MagicMock()
    engine_instance.run = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(flow, "ScraperEngine", MagicMock(return_value=engine_instance))
    monkeypatch.setattr(flow, "print_result_summary", MagicMock())
    monkeypatch.setattr(flow, "format_result_summary", MagicMock(return_value=""))

    await flow.run_flow()

    get_last_date_mock.assert_awaited_once()
    called_portal, called_connection_string = get_last_date_mock.await_args.args
    assert called_portal is fake_portal
    assert called_connection_string == "mssql+pyodbc://dummy"


@pytest.mark.asyncio
async def test_run_flow_raises_without_connection_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import portals.carburos_metalicos.flow as flow

    fake_portal = MagicMock()
    fake_registry = MagicMock()
    fake_registry.get.return_value = fake_portal
    monkeypatch.setattr(flow.PortalRegistry, "load", MagicMock(return_value=fake_registry))

    monkeypatch.setattr(flow, "DOWNLOAD_DIR", tmp_path / "downloads")
    monkeypatch.setattr(flow, "LOG_DIR", tmp_path / "logs")
    monkeypatch.delenv("SCRAPER_DB_CONNECTION_STRING", raising=False)

    with pytest.raises(RuntimeError, match="SCRAPER_DB_CONNECTION_STRING"):
        await flow.run_flow()
