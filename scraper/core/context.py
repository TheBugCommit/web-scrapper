"""
scraper.core.context
~~~~~~~~~~~~~~~~~~~~
Immutable configuration container for a scraping run.
All values are passed explicitly; no environment variables are read by the library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScraperContext:
    """Shared, read-only configuration passed throughout the scraping pipeline.

    All fields have sensible static defaults. Explicit constructor arguments
    always take precedence.

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
    max_depth: int = 5
    max_concurrent: int = 10
    debug_mode: bool = False
    rate_limit_delay: float = 1.0
    max_retries: int = 5
    download_dir: Path = field(default_factory=lambda: Path("./downloads"))
    headless: bool = True
    db_connection_string: str = ""
    db_table: str = "scraped_data"
    extra: dict[str, Any] = field(default_factory=dict)
