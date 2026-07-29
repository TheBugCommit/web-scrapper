"""
scraper.core.engine
~~~~~~~~~~~~~~~~~~~
Async scraping engine that orchestrates the full pipeline:

  Auth → [Concurrent workers] → Navigate → Extract → Store

Architecture
------------
The engine uses an :class:`asyncio.Queue` as a bounded work-queue fed by
navigators and drained by a configurable pool of ``max_concurrent`` worker
coroutines.  This ensures we never saturate the target server while still
exploiting I/O concurrency.

Lifecycle events are broadcast via :mod:`scraper.events.dispatcher` so that
listeners (logging, monitoring) can hook in without coupling to the engine.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

from scraper.core.session import ScraperSession
from scraper.events.dispatcher import EventDispatcher
from scraper.utils.logging import configure_logging, get_logger
from scraper.utils.url import normalise, same_domain

logger = get_logger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class PageResult:
    """Data extracted from a single page."""

    url: str
    status_code: int
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ScrapeResult:
    """Aggregate result of a complete scraping run."""

    pages: list[PageResult] = field(default_factory=list)
    errors: list[PageResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def total(self) -> int:
        return len(self.pages) + len(self.errors)


# ── Engine ────────────────────────────────────────────────────────────────────


class ScraperEngine:
    """Async engine that runs a :class:`~scraper.core.session.ScraperSession`.

    Parameters:
        session:    A fully-configured session produced by ``ScraperBuilder``.
        dispatcher: Optional event dispatcher for lifecycle hooks.
    """

    def __init__(
        self,
        session: ScraperSession,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._session = session
        self._dispatcher = dispatcher or EventDispatcher()
        self._visited: set[str] = set()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._result = ScrapeResult()

    # ── Public API ────────────────────────────────────────────────────────

    async def run(self) -> ScrapeResult:
        """Execute the scraping session and return aggregated results."""
        configure_logging()
        ctx = self._session.context
        backend = self._session.backend

        logger.info(
            "🚀 Starting scraping session  urls=%s  workers=%d",
            self._session.start_urls,
            ctx.max_concurrent,
        )
        start = time.monotonic()

        try:
            async with backend:
                if self._session.storage is not None:
                    await self._session.storage.open()
                try:
                    # ── 1. Authenticate ───────────────────────────────────────
                    if self._session.auth is not None:
                        logger.debug("🔐 Authenticating…")
                        await self._session.auth.authenticate(backend, ctx)
                        await self._dispatcher.emit("auth.success", {"context": ctx})

                    # ── 2. Seed the queue ─────────────────────────────────────
                    for url in self._session.start_urls:
                        normalised = normalise(url)
                        self._visited.add(normalised)
                        await self._queue.put(normalised)

                    # ── 3. Launch worker pool ─────────────────────────────────
                    workers = [
                        asyncio.create_task(self._worker(worker_id=i))
                        for i in range(ctx.max_concurrent)
                    ]

                    # Wait for the queue to drain, then cancel workers
                    await self._queue.join()
                    for w in workers:
                        w.cancel()
                    await asyncio.gather(*workers, return_exceptions=True)
                finally:
                    if self._session.storage is not None:
                        await self._session.storage.close()
        except Exception as exc:
            logger.error("ScraperEngine: execution failed — %s", exc, exc_info=True)
            raise

        self._result.duration_seconds = time.monotonic() - start
        logger.info(
            "✅ Done  pages=%d  errors=%d  duration=%.1fs",
            len(self._result.pages),
            len(self._result.errors),
            self._result.duration_seconds,
        )
        return self._result

    # ── Workers ───────────────────────────────────────────────────────────

    async def _worker(self, worker_id: int) -> None:
        """Consumer coroutine — processes URLs from the shared queue."""
        ctx = self._session.context
        while True:
            url = await self._queue.get()
            try:
                logger.debug("[worker-%d] Fetching %s", worker_id, url)
                await self._process_url(url)
            except asyncio.CancelledError:
                self._queue.task_done()
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error("[worker-%d] Error on %s: %s", worker_id, url, exc, exc_info=True)
                result = PageResult(url=url, status_code=0, error=str(exc))
                self._result.errors.append(result)
                await self._dispatcher.emit("page.error", {"url": url, "error": str(exc)})
            finally:
                self._queue.task_done()

            # Rate limiting — pause between requests
            if ctx.rate_limit_delay > 0:
                await asyncio.sleep(ctx.rate_limit_delay)

    async def _process_url(self, url: str) -> None:
        """Fetch one URL, run interactions, extract data, persist it, and enqueue new links."""
        session = self._session
        ctx = session.context

        # ── Fetch (with or without page interactions) ──────────────────────
        has_interactors = bool(session.interactors)
        supports_interactive = hasattr(session.backend, "get_interactive")

        if has_interactors and supports_interactive:
            get_interactive_fn = getattr(session.backend, "get_interactive")
            response = await get_interactive_fn(url, session.interactors, ctx)
        else:
            response = await session.backend.get(url)

        await self._dispatcher.emit("page.loaded", {"url": url, "status": response.status_code})

        # ── Extract ────────────────────────────────────────────────────────
        merged_data: dict[str, Any] = {"_url": url, "_status": response.status_code}

        # Surface any downloaded files from the interaction layer
        downloads = response.metadata.get("downloads", [])
        if downloads:
            merged_data["_downloads"] = downloads
            logger.info("  Downloads: %s", downloads)
            for dl_path in downloads:
                size_bytes = os.path.getsize(dl_path) if os.path.exists(dl_path) else 0
                await self._dispatcher.emit(
                    "file.downloaded",
                    {"url": url, "path": dl_path, "size_bytes": size_bytes},
                )

        has_extracted_data = False
        for extractor in session.extractors:
            extracted = await extractor.extract(response)
            if extracted:
                has_extracted_data = True
                merged_data.update(extracted)

        page_result = PageResult(url=url, status_code=response.status_code, data=merged_data)
        self._result.pages.append(page_result)
        await self._dispatcher.emit("data.extracted", {"url": url, "data": merged_data})

        # ── Store ──────────────────────────────────────────────────────────
        if session.storage is not None and has_extracted_data:
            table = getattr(session.storage, "_table", "unknown")
            schema = getattr(session.storage, "_schema", "")
            upsert_key = getattr(session.storage, "_upsert_key", None)
            try:
                rows = merged_data.get("_rows")
                if isinstance(rows, list):
                    if not rows:
                        await self._dispatcher.emit(
                            "storage.skipped",
                            {
                                "url": url,
                                "rows": 0,
                                "table": table,
                                "schema": schema,
                                "reason": "empty_records",
                                "status": "skipped",
                            },
                        )
                    else:
                        await session.storage.save_many(rows)
                        await self._dispatcher.emit(
                            "storage.saved",
                            {
                                "url": url,
                                "rows": len(rows),
                                "table": table,
                                "schema": schema,
                                "upsert_key": upsert_key,
                                "status": "saved",
                            },
                        )
                else:
                    data_to_save = {k: v for k, v in merged_data.items() if not k.startswith("_")}
                    if data_to_save:
                        await session.storage.save(data_to_save)
                        await self._dispatcher.emit(
                            "storage.saved",
                            {
                                "url": url,
                                "rows": 1,
                                "table": table,
                                "schema": schema,
                                "upsert_key": upsert_key,
                                "status": "saved",
                            },
                        )
                    else:
                        await self._dispatcher.emit(
                            "storage.skipped",
                            {
                                "url": url,
                                "rows": 0,
                                "table": table,
                                "schema": schema,
                                "reason": "empty_records",
                                "status": "skipped",
                            },
                        )
            except Exception as exc:
                await self._dispatcher.emit(
                    "storage.error",
                    {
                        "url": url,
                        "table": table,
                        "schema": schema,
                        "error": str(exc),
                        "status": "error",
                    },
                )
                logger.error("ScraperEngine: storage error for %s — %s", url, exc)
                raise

        # ── Discover next URLs ─────────────────────────────────────────────
        for navigator in session.navigators:
            next_urls = await navigator.discover(response, ctx)
            for next_url in next_urls:
                norm = normalise(next_url)
                if norm not in self._visited and same_domain(norm, url):
                    self._visited.add(norm)
                    await self._queue.put(norm)
                    logger.debug("  → Enqueued %s", norm)
