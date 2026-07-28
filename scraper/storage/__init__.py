"""scraper.storage — data persistence sinks."""

from .base import AbstractStorage
from .sqlserver_storage import SQLServerStorage

__all__ = ["AbstractStorage", "SQLServerStorage"]
