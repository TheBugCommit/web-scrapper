"""scraper.utils — utility helpers."""

from .cookies import dismiss_cookie_banners
from .csv import read_csv_rows
from .excel import read_excel_rows
from .logging import configure_logging, get_logger
from .url import extract_links, is_navigable, normalise, same_domain, same_origin

__all__ = [
    "configure_logging",
    "dismiss_cookie_banners",
    "get_logger",
    "extract_links",
    "is_navigable",
    "normalise",
    "read_csv_rows",
    "read_excel_rows",
    "same_domain",
    "same_origin",
]
