"""
scraper.utils.logging
~~~~~~~~~~~~~~~~~~~~~
Structured, colourised logging via the `rich` library.
All library code should obtain its logger via `get_logger(__name__)`.
"""

from __future__ import annotations

import logging
import os

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)
_INITIALIZED = False


def configure_logging(debug: bool = False) -> None:
    """Configure root logging for the scraper library.

    Call once at application startup (the engine does this automatically).
    Subsequent calls are no-ops.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=_console,
                rich_tracebacks=True,
                show_path=debug,
                markup=True,
            )
        ],
    )

    # Silence noisy third-party loggers unless we are in debug mode
    if not debug:
        for noisy in ("playwright", "urllib3", "httpx", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a library logger.  The name should be ``__name__``."""
    # Honour the SCRAPER_DEBUG env var so that importing the library is enough
    # to activate debug logging without having to call configure_logging().
    debug = os.getenv("SCRAPER_DEBUG", "false").lower() in ("1", "true", "yes")
    configure_logging(debug=debug)
    return logging.getLogger(name)
