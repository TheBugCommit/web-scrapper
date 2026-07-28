"""
scraper.navigation.base
~~~~~~~~~~~~~~~~~~~~~~~~
Abstract base class for all navigation strategies.

A navigator is responsible for discovering the **next set of URLs** to scrape
from a page that has already been fetched.  Multiple navigators can be chained
on the same session; their URL lists are merged and de-duplicated by the engine.

Common implementations:
- :class:`~scraper.navigation.link_navigator.LinkNavigator` — follow ``<a>`` links
- :class:`~scraper.navigation.pagination_navigator.PaginationNavigator` — handle paginated lists
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse
    from scraper.core.context import ScraperContext


class AbstractNavigator(ABC):
    """Plugin interface for link-discovery strategies.

    Implement this class to teach the engine how to find new pages.

    Example — navigate only to product URLs::

        class ProductNavigator(AbstractNavigator):
            async def discover(
                self, page: PageResponse, context: ScraperContext
            ) -> list[str]:
                soup = BeautifulSoup(page.content, "lxml")
                return [
                    a["href"] for a in soup.select("a.product-link")
                ]
    """

    @abstractmethod
    async def discover(
        self, page: "PageResponse", context: "ScraperContext"
    ) -> list[str]:
        """Return a list of URLs discovered from *page*.

        The engine will normalise, de-duplicate, and same-origin-filter the
        returned URLs before enqueueing them.

        Args:
            page:    The already-fetched page response.
            context: Shared scraping configuration.

        Returns:
            A (possibly empty) list of absolute or relative URLs.
        """
