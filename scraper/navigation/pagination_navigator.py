"""
scraper.navigation.pagination_navigator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Navigator that handles classic paginated lists:

- **Link-based pagination**: finds a "next page" anchor by CSS selector.
- **Query-string pagination**: increments a ``?page=N`` query parameter.
- **Infinite scroll** (Playwright only): scrolls to the bottom of the page
  and waits for new content to load.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from scraper.navigation.base import AbstractNavigator
from scraper.utils.logging import get_logger
from scraper.utils.url import normalise

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse
    from scraper.core.context import ScraperContext

logger = get_logger(__name__)


class PaginationNavigator(AbstractNavigator):
    """Navigate through paginated result sets.

    Parameters:
        next_selector:   CSS selector of the "next page" anchor.
                         If *None*, falls back to query-string mode.
        page_param:      Query-string parameter name for page number
                         (used when *next_selector* is not found).
        start_page:      First page number (default: 1).
        max_pages:       Stop after this many pages (0 = unlimited).
    """

    def __init__(
        self,
        next_selector: str | None = "a[rel=next], .pagination .next a, a.next-page",
        page_param: str = "page",
        start_page: int = 1,
        max_pages: int = 0,
    ) -> None:
        self._next_selector = next_selector
        self._page_param = page_param
        self._start_page = start_page
        self._max_pages = max_pages
        self._page_counter: dict[str, int] = {}  # keyed by base URL

    async def discover(
        self, page: "PageResponse", context: "ScraperContext"
    ) -> list[str]:
        # ── Strategy 1: CSS selector for explicit "next" link ──────────
        if self._next_selector:
            soup = BeautifulSoup(page.content, "lxml")
            next_tag = soup.select_one(self._next_selector)
            if next_tag and next_tag.get("href"):
                href: str = next_tag["href"]  # type: ignore[assignment]
                next_url = normalise(href, base=page.url)
                logger.debug("PaginationNavigator: next link → %s", next_url)
                return [next_url]

        # ── Strategy 2: Increment ?page= query-string param ────────────
        parsed = urlparse(page.url)
        qs = parse_qs(parsed.query, keep_blank_values=True)

        base_key = urlunparse(parsed._replace(query="", fragment=""))
        current = self._page_counter.get(base_key, self._start_page)
        next_page = current + 1

        if self._max_pages and next_page > self._max_pages:
            logger.debug("PaginationNavigator: max pages (%d) reached", self._max_pages)
            return []

        self._page_counter[base_key] = next_page
        qs[self._page_param] = [str(next_page)]
        next_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
        logger.debug("PaginationNavigator: page %d → %s", next_page, next_url)
        return [next_url]
