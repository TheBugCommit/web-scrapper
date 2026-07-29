"""
scraper.utils.logging
~~~~~~~~~~~~~~~~~~~~~
Structured, colourised logging via the `rich` library and rotating file logs.

All library code should obtain its logger via `get_logger(__name__)`.

Environment Variables:
    SCRAPER_DEBUG:          enable debug logging (default: false)
    SCRAPER_LOG_ENABLED:    enable rotating file logs (default: true)
    SCRAPER_LOG_DIR:        directory where log files are written (default: ./logs)
    SCRAPER_LOG_MAX_BYTES:  maximum size in bytes per log file (default: 10485760 = 10 MB)
    SCRAPER_LOG_BACKUPS:    number of backup log files to retain (default: 5)

Log files generated in `SCRAPER_LOG_DIR`:
    - `scraper.log` : All log messages at the configured level (INFO/DEBUG).
    - `error.log`   : Only ERROR and CRITICAL messages for fast troubleshooting.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)
_INITIALIZED = False


def configure_logging(
    debug: bool = False,
    log_dir: str | Path | None = "./logs",
    enable_file_logging: bool = True,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
) -> None:
    """Configure root logging for the scraper library.

    Sets up:
    - Colourised console output via `rich`.
    - Rotating file logging (`scraper.log` for general logs, `error.log` for errors).

    Call once at application startup (the engine does this automatically).
    Subsequent calls are no-ops.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    level = logging.DEBUG if debug else logging.INFO

    handlers: list[logging.Handler] = [
        RichHandler(
            console=_console,
            rich_tracebacks=True,
            show_path=debug,
            markup=True,
        )
    ]

    # ── Rotating Log Files ────────────────────────────────────────────────────
    if enable_file_logging and log_dir:
        target_dir = Path(log_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        file_formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 1. General log file (all messages at current level)
        general_file = target_dir / "scraper.log"
        fh_general = RotatingFileHandler(
            general_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh_general.setLevel(level)
        fh_general.setFormatter(file_formatter)
        handlers.append(fh_general)

        # 2. Error log file (only ERROR and CRITICAL messages)
        error_file = target_dir / "error.log"
        fh_error = RotatingFileHandler(
            error_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh_error.setLevel(logging.ERROR)
        fh_error.setFormatter(file_formatter)
        handlers.append(fh_error)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )

    # Silence noisy third-party loggers unless we are in debug mode
    if not debug:
        for noisy in ("playwright", "urllib3", "httpx", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a library logger. The name should be ``__name__``."""
    configure_logging()
    return logging.getLogger(name)
