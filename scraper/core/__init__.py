"""scraper.core — engine, session, context, builder."""

from .builder import ScraperBuilder
from .context import ScraperContext
from .engine import PageResult, ScrapeResult, ScraperEngine
from .session import ScraperSession

__all__ = [
    "ScraperBuilder",
    "ScraperContext",
    "ScraperEngine",
    "ScraperSession",
    "PageResult",
    "ScrapeResult",
]
