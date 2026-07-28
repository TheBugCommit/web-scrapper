"""scraper.extractors — data extraction strategies."""

from .base import AbstractExtractor
from .css_extractor import CSSExtractor, CSSRule
from .excel_extractor import ExcelExtractor
from .file_downloader import FileDownloader
from .xpath_extractor import XPathExtractor, XPathRule

__all__ = [
    "AbstractExtractor",
    "CSSExtractor",
    "CSSRule",
    "ExcelExtractor",
    "XPathExtractor",
    "XPathRule",
    "FileDownloader",
]
