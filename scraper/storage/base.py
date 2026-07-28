"""
scraper.storage.base
~~~~~~~~~~~~~~~~~~~~~
Abstract base class for all storage sinks.

A storage sink receives the flat dictionary produced by the extractor chain
and persists it somewhere (SQL Server, flat file, REST API, etc.).

Implement this class to add a new output target::

    class MyStorage(AbstractStorage):
        async def save(self, data: dict[str, Any]) -> None:
            await my_db.insert(data)

        async def save_many(self, rows: list[dict[str, Any]]) -> None:
            await my_db.bulk_insert(rows)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AbstractStorage(ABC):
    """Plugin interface for data persistence backends."""

    async def __aenter__(self) -> "AbstractStorage":
        await self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def open(self) -> None:
        """Initialise the storage connection / resource pool."""

    async def close(self) -> None:
        """Release storage resources."""

    @abstractmethod
    async def save(self, data: dict[str, Any]) -> None:
        """Persist a single extracted row.

        Args:
            data: Flat ``{column: value}`` dictionary.
        """

    async def save_many(self, rows: list[dict[str, Any]]) -> None:
        """Persist multiple rows.  Default implementation calls :meth:`save` in a loop."""
        for row in rows:
            await self.save(row)
