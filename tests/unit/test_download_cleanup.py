"""Unit tests for scraper.events.cleanup.register_download_cleanup — the IoC
hook that deletes a URL's downloaded file(s) once a caller-chosen event fires
for it (default: only after storage.saved, so a failed/skipped save leaves
the file in place)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scraper.events.cleanup import register_download_cleanup
from scraper.events.dispatcher import EventDispatcher


@pytest.mark.asyncio
async def test_cleanup_deletes_file_after_storage_saved(tmp_path: Path) -> None:
    downloaded = tmp_path / "readings.csv"
    downloaded.write_text("data", encoding="utf-8")

    dispatcher = EventDispatcher()
    register_download_cleanup(dispatcher)

    await dispatcher.emit(
        "file.downloaded",
        {"url": "https://example.com/x", "path": str(downloaded), "size_bytes": 4},
    )
    assert downloaded.exists()

    await dispatcher.emit(
        "storage.saved",
        {"url": "https://example.com/x", "rows": 3, "table": "t", "schema": "dbo", "upsert_key": None},
    )

    assert not downloaded.exists()


@pytest.mark.asyncio
async def test_cleanup_keeps_file_on_storage_error_by_default(tmp_path: Path) -> None:
    downloaded = tmp_path / "readings.csv"
    downloaded.write_text("data", encoding="utf-8")

    dispatcher = EventDispatcher()
    register_download_cleanup(dispatcher)

    await dispatcher.emit(
        "file.downloaded",
        {"url": "https://example.com/x", "path": str(downloaded), "size_bytes": 4},
    )
    await dispatcher.emit(
        "storage.error",
        {"url": "https://example.com/x", "table": "t", "schema": "dbo", "error": "db offline"},
    )

    assert downloaded.exists()


@pytest.mark.asyncio
async def test_cleanup_honours_custom_on_events(tmp_path: Path) -> None:
    downloaded = tmp_path / "empty.csv"
    downloaded.write_text("", encoding="utf-8")

    dispatcher = EventDispatcher()
    register_download_cleanup(dispatcher, on_events=("storage.skipped",))

    await dispatcher.emit(
        "file.downloaded",
        {"url": "https://example.com/y", "path": str(downloaded), "size_bytes": 0},
    )
    await dispatcher.emit(
        "storage.skipped",
        {"url": "https://example.com/y", "rows": 0, "table": "t", "schema": "dbo", "reason": "empty_records"},
    )

    assert not downloaded.exists()


@pytest.mark.asyncio
async def test_cleanup_honours_condition_predicate(tmp_path: Path) -> None:
    downloaded = tmp_path / "readings.csv"
    downloaded.write_text("data", encoding="utf-8")

    dispatcher = EventDispatcher()
    register_download_cleanup(dispatcher, condition=lambda payload: payload["rows"] > 0)

    await dispatcher.emit(
        "file.downloaded",
        {"url": "https://example.com/z", "path": str(downloaded), "size_bytes": 4},
    )
    await dispatcher.emit(
        "storage.saved",
        {"url": "https://example.com/z", "rows": 0, "table": "t", "schema": "dbo", "upsert_key": None},
    )

    assert downloaded.exists()
