"""
scraper — Extensible async web scraping engine.

Quick start::

    import asyncio
    from scraper import ScraperBuilder
    from scraper.backends import RequestsBackend
    from scraper.extractors import CSSExtractor

    async def main():
        session = (
            ScraperBuilder()
            .with_url("https://books.toscrape.com")
            .with_backend(RequestsBackend())
            .with_extractor(CSSExtractor(rules={"title": "h1", "price": ".price_color"}))
            .build()
        )
        result = await session.run()
        for page in result.pages:
            print(page.data)

    asyncio.run(main())
"""

from scraper.core.builder import ScraperBuilder
from scraper.core.context import ScraperContext
from scraper.core.engine import PageResult, ScrapeResult, ScraperEngine
from scraper.core.session import ScraperSession
from scraper.utils.reporting import format_result_summary, print_result_summary

__all__ = [
    "ScraperBuilder",
    "ScraperContext",
    "ScraperEngine",
    "ScraperSession",
    "PageResult",
    "ScrapeResult",
    "format_result_summary",
    "print_result_summary",
]

__version__ = "0.2.0"
