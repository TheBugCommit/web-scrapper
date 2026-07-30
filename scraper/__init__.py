from scraper.core.builder import ScraperBuilder
from scraper.core.context import ScraperContext
from scraper.core.engine import PageResult, ScrapeResult, ScraperEngine
from scraper.core.session import ScraperSession
from scraper.events.cleanup import register_download_cleanup
from scraper.events.default_handlers import create_default_dispatcher
from scraper.events.dispatcher import EventDispatcher
from scraper.extractors.csv_extractor import CSVExtractor
from scraper.extractors.excel_extractor import ExcelExtractor
from scraper.interaction import Key, KeyCombo, PressKeyAction
from scraper.navigation import LinkNavigator, PaginationNavigator
from scraper.storage.criteria import Criteria, FilterOperator, OrderDirection
from scraper.storage.repository import SQLServerRepository, get_portal_last_date
from scraper.utils.csv import read_csv_rows
from scraper.utils.excel import read_excel_rows
from scraper.utils.reporting import format_result_summary, print_result_summary

__all__ = [
    "Criteria",
    "CSVExtractor",
    "EventDispatcher",
    "ExcelExtractor",
    "FilterOperator",
    "Key",
    "KeyCombo",
    "LinkNavigator",
    "OrderDirection",
    "PageResult",
    "PaginationNavigator",
    "PressKeyAction",
    "SQLServerRepository",
    "ScrapeResult",
    "ScraperBuilder",
    "ScraperContext",
    "ScraperEngine",
    "ScraperSession",
    "create_default_dispatcher",
    "format_result_summary",
    "get_portal_last_date",
    "print_result_summary",
    "read_csv_rows",
    "read_excel_rows",
    "register_download_cleanup",
]

__version__ = "0.2.0"
