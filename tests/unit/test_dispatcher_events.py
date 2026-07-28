"""Unit tests for ScraperEngine dispatcher events."""

from __future__ import annotations

import asyncio
import pytest
from scraper.events.dispatcher import EventDispatcher


@pytest.mark.asyncio
async def test_dispatcher_storage_events() -> None:
    dispatcher = EventDispatcher()
    events_received: list[tuple[str, dict]] = []

    @dispatcher.on("storage.saved")
    def on_saved(payload: dict) -> None:
        events_received.append(("storage.saved", payload))

    @dispatcher.on("storage.skipped")
    def on_skipped(payload: dict) -> None:
        events_received.append(("storage.skipped", payload))

    @dispatcher.on("storage.error")
    def on_error(payload: dict) -> None:
        events_received.append(("storage.error", payload))

    await dispatcher.emit(
        "storage.saved",
        {"url": "http://test", "rows": 10, "table": "t1", "schema": "dbo", "upsert_key": "id"},
    )
    await dispatcher.emit(
        "storage.skipped",
        {"url": "http://test", "rows": 0, "table": "t1", "schema": "dbo", "reason": "empty"},
    )
    await dispatcher.emit(
        "storage.error",
        {"url": "http://test", "table": "t1", "schema": "dbo", "error": "db offline"},
    )

    assert len(events_received) == 3
    assert events_received[0][0] == "storage.saved"
    assert events_received[0][1]["rows"] == 10
    assert events_received[1][0] == "storage.skipped"
    assert events_received[2][0] == "storage.error"
    assert "offline" in events_received[2][1]["error"]


@pytest.mark.asyncio
async def test_engine_storage_lifecycle() -> None:
    from typing import Any
    from scraper import ScraperBuilder, ScraperEngine
    from scraper.backends.base import AbstractBackend, PageResponse
    from scraper.storage.base import AbstractStorage

    class DummyBackend(AbstractBackend):
        async def fetch(self, url: str, **kwargs: Any) -> PageResponse:
            return PageResponse(url=url, status_code=200, content="<html></html>")

        async def get(self, url: str, **kwargs: Any) -> PageResponse:
            return PageResponse(url=url, status_code=200, content="<html></html>")

        async def post(self, url: str, **kwargs: Any) -> PageResponse:
            return PageResponse(url=url, status_code=200, content="<html></html>")

    class DummyStorage(AbstractStorage):
        def __init__(self) -> None:
            self.opened = False
            self.closed = False

        async def open(self) -> None:
            self.opened = True

        async def close(self) -> None:
            self.closed = True

        async def save(self, data: dict[str, Any]) -> None:
            pass

    storage = DummyStorage()
    session = (
        ScraperBuilder()
        .with_url("https://example.com")
        .with_backend(DummyBackend())
        .with_storage(storage)
        .build()
    )
    engine = ScraperEngine(session)
    await engine.run()

    assert storage.opened is True
    assert storage.closed is True


