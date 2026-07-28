"""
scraper.extractors.base
~~~~~~~~~~~~~~~~~~~~~~~~
Abstract base class for all data extractors.

An extractor receives a :class:`~scraper.backends.base.PageResponse` and
returns a flat dictionary of field → value pairs.  Multiple extractors can be
chained; their outputs are merged by the engine (later extractors win on key
conflicts).

Implement this class to define a new extraction strategy::

    class MyExtractor(AbstractExtractor):
        async def extract(self, page: PageResponse) -> dict[str, Any]:
            soup = BeautifulSoup(page.content, "lxml")
            return {"title": soup.title.string}
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse


class AbstractExtractor(ABC):
    """Plugin interface for data extraction strategies."""

    @abstractmethod
    async def extract(self, page: "PageResponse") -> dict[str, Any]:
        """Extract structured data from *page*.

        Args:
            page: A fully-fetched page (HTML content + metadata).

        Returns:
            A flat ``{field_name: value}`` dictionary.  Values may be
            strings, numbers, lists, or ``None``.
        """
