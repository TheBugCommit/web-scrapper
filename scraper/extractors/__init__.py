"""scraper.extractors — data extraction strategies."""

from .base import AbstractExtractor
from .css_extractor import CSSExtractor, CSSRule
from .csv_extractor import CSVExtractor
from .excel_extractor import ExcelExtractor
from .file_downloader import FileDownloader
from .xpath_extractor import XPathExtractor, XPathRule

__all__ = [
    "AbstractExtractor",
    "CSSExtractor",
    "CSSRule",
    "CSVExtractor",
    "ExcelExtractor",
    "XPathExtractor",
    "XPathRule",
    "FileDownloader",
]
