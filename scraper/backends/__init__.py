"""scraper.backends — HTTP and browser backends."""

from .base import AbstractBackend, PageResponse
from .playwright_backend import PlaywrightBackend
from .requests_backend import RequestsBackend

__all__ = ["AbstractBackend", "PageResponse", "RequestsBackend", "PlaywrightBackend"]
