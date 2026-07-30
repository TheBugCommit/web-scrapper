"""
scraper.navigation.link_navigator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
General-purpose navigator that follows all ``<a href>`` links found on a page.

Optional filters let you restrict navigation to specific URL patterns,
CSS-selector-matched anchors, or links matching a regex.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scraper.navigation.base import AbstractNavigator
from scraper.utils.logging import get_logger
from scraper.utils.url import extract_links, same_domain

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse
    from scraper.core.context import ScraperContext

logger = get_logger(__name__)


class LinkNavigator(AbstractNavigator):
    """Follow all ``<a href>`` links found on a page.

    Parameters:
        css_filter:    Only follow links matching this CSS selector
                       (e.g. ``"nav a"``, ``".content a"``).
        url_pattern:   Only follow links whose absolute URL matches this regex.
        max_links:     Maximum links to return per page (0 = unlimited).
        same_origin:   If *True* (default) only return same-domain links (this
                       flag name is kept for backward compatibility, but the
                       check is deliberately domain-based, not origin-based —
                       crawling generally wants to follow subdomains too. Use
                       :class:`~scraper.debug.crawler.DebugCrawler` if you need
                       strict same-origin behaviour for site-mapping instead.
    """

    def __init__(
        self,
        css_filter: str = "a[href]",
        url_pattern: str | None = None,
        max_links: int = 0,
        same_origin: bool = True,
    ) -> None:
        self._css_filter = css_filter
        self._url_re = re.compile(url_pattern) if url_pattern else None
        self._max_links = max_links
        self._same_origin = same_origin

    async def discover(
        self, page: "PageResponse", context: "ScraperContext"
    ) -> list[str]:
        candidates = extract_links(page.content, page.url, selector=self._css_filter)

        found: list[str] = []
        for abs_url in candidates:
            if self._same_origin and not same_domain(abs_url, page.url):
                continue
            if self._url_re and not self._url_re.search(abs_url):
                continue

            found.append(abs_url)

            if self._max_links and len(found) >= self._max_links:
                break

        logger.debug("LinkNavigator: found %d links on %s", len(found), page.url)
        return found
