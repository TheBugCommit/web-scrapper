"""scraper.navigation — page discovery strategies."""

from .base import AbstractNavigator
from .link_navigator import LinkNavigator
from .pagination_navigator import PaginationNavigator

__all__ = ["AbstractNavigator", "LinkNavigator", "PaginationNavigator"]
