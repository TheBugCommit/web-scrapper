"""
scraper.events.cleanup
~~~~~~~~~~~~~~~~~~~~~~~
Opt-in IoC hook that deletes a URL's downloaded file(s) once the caller-chosen
event(s) fire for that URL. Nothing is deleted unless a caller explicitly
registers this — the engine and :func:`~scraper.events.default_handlers.create_default_dispatcher`
never delete files on their own.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from scraper.events.dispatcher import EventDispatcher
from scraper.utils.logging import get_logger


def register_download_cleanup(
    dispatcher: EventDispatcher,
    on_events: tuple[str, ...] = ("storage.saved",),
    condition: Callable[[dict[str, Any]], bool] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Delete a URL's downloaded file(s) once one of *on_events* fires for it.

    Tracks paths from ``file.downloaded`` events (keyed by URL) and removes
    them the first time any event in *on_events* fires for that same URL.
    By default this only reacts to ``storage.saved`` — i.e. a downloaded file
    is only ever deleted after its extracted rows have actually been
    persisted; a failed or empty save (``storage.error`` / ``storage.skipped``)
    leaves the file in place for inspection/retry.

    Both the trigger and the condition are left to the caller — this
    function only wires the file-tracking mechanics:

    Args:
        dispatcher: The dispatcher to attach handlers to.
        on_events:  Event names that should trigger cleanup for their URL.
            Defaults to ``("storage.saved",)``. Pass e.g.
            ``("storage.saved", "storage.skipped")`` to also clean up when
            nothing new was found to save.
        condition:  Optional predicate over the triggering event's payload;
            when it returns ``False`` the tracked files are kept instead of
            deleted (e.g. ``lambda p: p["rows"] > 0``).
        logger:     Logger to report deletions/failures to. Defaults to this
            module's logger.
    """
    log = logger or get_logger(__name__)
    pending: dict[str, list[str]] = {}

    @dispatcher.on("file.downloaded")
    def _track(payload: dict[str, Any]) -> None:
        pending.setdefault(payload["url"], []).append(payload["path"])

    def _cleanup(payload: dict[str, Any]) -> None:
        url = payload.get("url")
        
        if not isinstance(url, str):
            return

        paths = pending.pop(url, [])
        if not paths:
            return
        if condition is not None and not condition(payload):
            return
        for raw_path in paths:
            path = Path(raw_path)
            try:
                path.unlink(missing_ok=True)
                log.info("🗑️ Fitxer de descàrrega eliminat: %s", path)
            except OSError as exc:
                log.warning("No s'ha pogut eliminar %s: %s", path, exc)

    for event in on_events:
        dispatcher.on(event)(_cleanup)
