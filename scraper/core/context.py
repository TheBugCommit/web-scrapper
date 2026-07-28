"""
scraper.core.context
~~~~~~~~~~~~~~~~~~~~
Immutable configuration container for a scraping run.
All values can be overridden via environment variables (loaded from .env).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env on first import so every module benefits automatically.
load_dotenv(override=False)


@dataclass(frozen=True)
class ScraperContext:
    """Shared, read-only configuration passed throughout the scraping pipeline.

    All fields have sensible defaults that read from environment variables.
    Explicit constructor arguments always take precedence over env vars.

    Attributes:
        base_url:           Root URL for the scraping session.
        max_depth:          Maximum link-follow depth (used by DebugCrawler).
        max_concurrent:     Maximum number of concurrent page workers.
        debug_mode:         Enable verbose logging + DebugCrawler output.
        rate_limit_delay:   Seconds to wait between requests to the same host.
        max_retries:        Maximum retry attempts on transient failures.
        download_dir:       Directory for downloaded files.
        headless:           Run Playwright in headless mode.
        db_connection_string: SQLAlchemy connection string for SQL Server.
        db_table:           Target database table for scraped rows.
        extra:              Arbitrary key-value pairs for custom adapters.
    """

    base_url: str = ""
    max_depth: int = field(default_factory=lambda: int(os.getenv("SCRAPER_MAX_DEPTH", "5")))
    max_concurrent: int = field(
        default_factory=lambda: int(os.getenv("SCRAPER_MAX_CONCURRENT", "5"))
    )
    debug_mode: bool = field(
        default_factory=lambda: os.getenv("SCRAPER_DEBUG", "false").lower()
        in ("1", "true", "yes")
    )
    rate_limit_delay: float = field(
        default_factory=lambda: float(os.getenv("SCRAPER_RATE_LIMIT_DELAY", "1.0"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
    )
    download_dir: Path = field(
        default_factory=lambda: Path(os.getenv("SCRAPER_DOWNLOAD_DIR", "./downloads"))
    )
    headless: bool = field(
        default_factory=lambda: os.getenv("SCRAPER_HEADLESS", "true").lower()
        in ("1", "true", "yes")
    )
    db_connection_string: str = field(
        default_factory=lambda: os.getenv("SCRAPER_DB_CONNECTION_STRING", "")
    )
    db_table: str = field(
        default_factory=lambda: os.getenv("SCRAPER_DB_TABLE", "scraped_data")
    )
    extra: dict[str, str] = field(default_factory=dict)
