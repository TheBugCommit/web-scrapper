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
from scraper.events.dispatcher import EventDispatcher
from scraper.extractors.excel_extractor import ExcelExtractor
from scraper.storage.criteria import Criteria, FilterOperator, OrderDirection
from scraper.storage.repository import SQLServerRepository, get_portal_last_date
from scraper.utils.excel import read_excel_rows
from scraper.utils.reporting import format_result_summary, print_result_summary

__all__ = [
    "Criteria",
    "EventDispatcher",
    "ExcelExtractor",
    "FilterOperator",
    "OrderDirection",
    "PageResult",
    "SQLServerRepository",
    "ScrapeResult",
    "ScraperBuilder",
    "ScraperContext",
    "ScraperEngine",
    "ScraperSession",
    "format_result_summary",
    "get_portal_last_date",
    "print_result_summary",
    "read_excel_rows",
]

__version__ = "0.2.0"
