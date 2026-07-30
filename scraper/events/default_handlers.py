"""
scraper.events.default_handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Factory for a pre-configured :class:`~scraper.events.dispatcher.EventDispatcher`
with the standard progress handlers shared by every portal flow (auth,
download, storage saved/skipped/error).

Every portal flow used to copy-paste the same five handlers verbatim. Call
:func:`create_default_dispatcher` instead and register any portal-specific
handlers on the returned dispatcher.
"""

from __future__ import annotations

import logging
from typing import Any

from scraper.events.dispatcher import EventDispatcher
from scraper.utils.logging import get_logger


def create_default_dispatcher(logger: logging.Logger | None = None) -> EventDispatcher:
    """Return an :class:`EventDispatcher` pre-registered with standard progress handlers.

    Registers handlers for ``auth.success``, ``file.downloaded``,
    ``storage.saved``, ``storage.skipped``, and ``storage.error`` that log
    human-readable progress lines. Portals call this instead of duplicating
    the handler block, and may register additional handlers on the returned
    dispatcher for portal-specific behaviour.

    Args:
        logger: Logger the handlers report to. Pass a portal-specific logger
            (e.g. from :func:`scraper.utils.logging.get_portal_logger`) so
            each portal's progress lands only in its own log file — this is
            what keeps concurrently-running portals from interleaving their
            output on the console. Defaults to this module's logger.
    """
    log = logger or get_logger(__name__)
    dispatcher = EventDispatcher()

    @dispatcher.on("auth.success")
    def on_auth(payload: dict[str, Any]) -> None:
        log.info("🔐 [Event: auth.success] Autenticació al portal completada amb èxit!")

    @dispatcher.on("file.downloaded")
    def on_download(payload: dict[str, Any]) -> None:
        log.info(
            "📥 [Event: file.downloaded] Fitxer descarregat: %s (%s bytes)",
            payload["path"],
            payload["size_bytes"],
        )

    @dispatcher.on("storage.saved")
    def on_saved(payload: dict[str, Any]) -> None:
        log.info(
            "🚀 [Event: storage.saved] Desats/upsertats %s registres a SQL Server "
            "[%s].[%s] (PK: %s)!",
            payload["rows"],
            payload["schema"],
            payload["table"],
            payload["upsert_key"],
        )

    @dispatcher.on("storage.skipped")
    def on_skipped(payload: dict[str, Any]) -> None:
        log.warning(
            "⚠️ [Event: storage.skipped] Cap registre per desar a [%s].[%s] (Motiu: %s)",
            payload["schema"],
            payload["table"],
            payload.get("reason"),
        )

    @dispatcher.on("storage.error")
    def on_error(payload: dict[str, Any]) -> None:
        log.error(
            "❌ [Event: storage.error] Error desant a [%s].[%s]: %s",
            payload["schema"],
            payload["table"],
            payload["error"],
        )

    return dispatcher
