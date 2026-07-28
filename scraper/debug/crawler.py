"""
scraper.debug.crawler
~~~~~~~~~~~~~~~~~~~~~~
Recursive debug crawler that maps all pages reachable from a seed URL.

Activated when ``SCRAPER_DEBUG=true`` or when used directly.

Features
--------
- BFS traversal (breadth-first, level by level up to ``max_depth``)
- Respects same-origin constraint (configurable)
- Returns a :class:`CrawlNode` tree that can be pretty-printed or serialised
- Concurrent fetching controlled by ``max_concurrent`` semaphore
- Works with both :class:`~scraper.backends.requests_backend.RequestsBackend`
  and :class:`~scraper.backends.playwright_backend.PlaywrightBackend`

Usage::

    import asyncio
    from scraper.backends import RequestsBackend
    from scraper.debug import DebugCrawler

    async def main():
        async with RequestsBackend() as backend:
            crawler = DebugCrawler(
                backend=backend,
                start_url="https://example.com",
                max_depth=3,
                max_concurrent=5,
            )
            root = await crawler.crawl()
            crawler.print_tree(root)
            crawler.export_json(root, "crawl_map.json")

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from scraper.utils.logging import get_logger
from scraper.utils.url import is_navigable, normalise, same_origin

if TYPE_CHECKING:
    from scraper.backends.base import AbstractBackend

logger = get_logger(__name__)


@dataclass
class CrawlNode:
    """A single node in the crawl map.

    Attributes:
        url:         The page URL.
        title:       Page ``<title>`` text (empty if not found).
        status_code: HTTP status code (0 if fetch failed).
        depth:       Link depth from the seed URL (0 = seed).
        error:       Error message if the page could not be fetched.
        children:    Directly linked child nodes (same-origin).
    """

    url: str
    title: str = ""
    status_code: int = 0
    depth: int = 0
    error: str | None = None
    children: list["CrawlNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Recursively serialise the tree to a plain dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "status_code": self.status_code,
            "depth": self.depth,
            "error": self.error,
            "children": [c.to_dict() for c in self.children],
        }


class DebugCrawler:
    """BFS crawler that recursively discovers all reachable pages.

    Parameters:
        backend:        An already-opened (or context-managed) backend.
        start_url:      Seed URL to begin crawling from.
        max_depth:      Maximum link-follow depth (0 = seed page only).
        max_concurrent: Maximum simultaneous page fetches.
        same_origin_only: Only follow links sharing the seed host (default: True).
        link_selector:  CSS selector for links to follow (default: ``"a[href]"``).
    """

    def __init__(
        self,
        backend: "AbstractBackend",
        start_url: str,
        max_depth: int = 3,
        max_concurrent: int = 5,
        same_origin_only: bool = True,
        link_selector: str = "a[href]",
    ) -> None:
        self._backend = backend
        self._start_url = normalise(start_url)
        self._max_depth = max_depth
        self._sem = asyncio.Semaphore(max_concurrent)
        self._same_origin_only = same_origin_only
        self._link_selector = link_selector
        self._visited: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────

    async def crawl(self) -> CrawlNode:
        """Run BFS and return the root :class:`CrawlNode`.

        The returned tree represents all discovered pages.  Pages at depth 0
        are the seed; children are pages linked from them, and so on.
        """
        logger.info(
            "🕷  DebugCrawler starting  seed=%s  max_depth=%d",
            self._start_url,
            self._max_depth,
        )
        self._visited.clear()
        root = await self._crawl_node(self._start_url, depth=0)
        total = self._count_nodes(root)
        logger.info("🕷  DebugCrawler finished  total_pages=%d", total)
        return root

    def print_tree(self, node: CrawlNode, indent: int = 0) -> None:
        """Pretty-print the crawl tree to stdout."""
        prefix = "  " * indent + ("├─ " if indent else "")
        status = f"[{node.status_code}]" if node.status_code else "[ERR]"
        title = f" — {node.title}" if node.title else ""
        print(f"{prefix}{status} {node.url}{title}")
        for child in node.children:
            self.print_tree(child, indent + 1)

    def export_json(self, node: CrawlNode, path: str) -> None:
        """Write the crawl tree to a JSON file at *path*."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(node.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("DebugCrawler: exported tree to %s", path)

    def all_urls(self, node: CrawlNode) -> list[str]:
        """Return a flat list of all discovered URLs (BFS order)."""
        result: list[str] = []
        queue = [node]
        while queue:
            n = queue.pop(0)
            result.append(n.url)
            queue.extend(n.children)
        return result

    # ── Internal ──────────────────────────────────────────────────────────

    async def _crawl_node(self, url: str, depth: int) -> CrawlNode:
        """Fetch *url* and recursively crawl its children up to max_depth."""
        self._visited.add(url)

        async with self._sem:
            try:
                response = await self._backend.get(url)
                title = self._extract_title(response.content)
                node = CrawlNode(
                    url=url,
                    title=title,
                    status_code=response.status_code,
                    depth=depth,
                )
                logger.debug("[depth=%d] %s  status=%d  title=%s", depth, url, response.status_code, title)
            except Exception as exc:  # noqa: BLE001
                logger.warning("DebugCrawler: failed %s — %s", url, exc)
                return CrawlNode(url=url, depth=depth, error=str(exc))

        # Recurse into children if we haven't hit max depth
        if depth < self._max_depth:
            child_urls = self._extract_links(response.content, url)
            child_tasks = [
                self._crawl_node(child_url, depth + 1)
                for child_url in child_urls
                if child_url not in self._visited
            ]
            # Mark as visited eagerly to avoid duplicate fetches
            for child_url in child_urls:
                self._visited.add(child_url)

            if child_tasks:
                children = await asyncio.gather(*child_tasks, return_exceptions=False)
                node.children = list(children)

        return node

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract and filter links from *html*."""
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for tag in soup.select(self._link_selector):
            href: str = tag.get("href", "").strip()
            if not href or href.startswith("#"):
                continue
            abs_url = normalise(href, base=base_url)
            if not is_navigable(abs_url):
                continue
            if self._same_origin_only and not same_origin(abs_url, self._start_url):
                continue
            if abs_url not in self._visited:
                links.append(abs_url)
        return links

    @staticmethod
    def _extract_title(html: str) -> str:
        """Extract the ``<title>`` text from an HTML page."""
        soup = BeautifulSoup(html, "lxml")
        tag = soup.find("title")
        return tag.get_text(strip=True) if tag else ""

    @staticmethod
    def _count_nodes(node: CrawlNode) -> int:
        return 1 + sum(DebugCrawler._count_nodes(c) for c in node.children)
