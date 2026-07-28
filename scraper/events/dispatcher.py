"""
scraper.events.dispatcher
~~~~~~~~~~~~~~~~~~~~~~~~~~
Lightweight observer / event system for the scraping lifecycle.

Consumers attach handlers (sync or async callables) to named events.
The engine emits events at key points so that monitoring, logging, or
custom side-effects can be implemented without modifying the core.

Built-in events
---------------
=======================  ==============================================================
Event name               Payload keys
=======================  ==============================================================
``auth.success``         ``context``
``page.loaded``          ``url``, ``status``
``page.error``           ``url``, ``error``
``data.extracted``       ``url``, ``data``
``file.downloaded``      ``url``, ``path``, ``size_bytes``
``storage.saved``        ``url``, ``rows``, ``table``, ``schema``, ``upsert_key``
``storage.skipped``      ``url``, ``rows``, ``table``, ``schema``, ``reason``
``storage.error``        ``url``, ``table``, ``schema``, ``error``
``run.started``          ``start_urls``, ``max_concurrent``
``run.finished``         ``pages``, ``errors``, ``duration``
=======================  ==============================================================

Example::

    from scraper.events import EventDispatcher

    dispatcher = EventDispatcher()

    @dispatcher.on("data.extracted")
    async def log_data(payload):
        print(f"Extracted from {payload['url']}: {payload['data']}")
"""

from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from typing import Any, Awaitable, Callable, Union

Handler = Callable[[dict[str, Any]], Union[None, Awaitable[None]]]


class EventDispatcher:
    """Simple async event dispatcher (observer pattern).

    Usage::

        dispatcher = EventDispatcher()

        # Register a handler (decorator style)
        @dispatcher.on("page.loaded")
        async def handle(payload):
            print(payload["url"])

        # Or imperatively
        dispatcher.on("page.loaded")(my_handler)

        # Emit an event
        await dispatcher.emit("page.loaded", {"url": "https://..."})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event: str) -> Callable[[Handler], Handler]:
        """Decorator / imperative registration for an event handler."""
        def decorator(handler: Handler) -> Handler:
            self._handlers[event].append(handler)
            return handler
        return decorator

    def off(self, event: str, handler: Handler) -> None:
        """Remove a specific handler from an event."""
        self._handlers[event] = [h for h in self._handlers[event] if h is not handler]

    def clear(self, event: str | None = None) -> None:
        """Remove all handlers (for a specific event or all events)."""
        if event:
            self._handlers[event].clear()
        else:
            self._handlers.clear()

    async def emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Invoke all handlers registered for *event*.

        Both sync and async handlers are supported.  Handlers are invoked
        sequentially in registration order.  Exceptions in handlers are logged
        but do not abort the scraping pipeline.

        Args:
            event:   Event name (e.g. ``"page.loaded"``).
            payload: Arbitrary data passed to each handler.
        """
        handlers = self._handlers.get(event, [])
        data = payload or {}

        for handler in handlers:
            try:
                result = handler(data)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).warning(
                    "EventDispatcher: handler %s for '%s' raised %s",
                    handler.__name__,
                    event,
                    exc,
                )
