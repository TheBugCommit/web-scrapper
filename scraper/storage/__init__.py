"""scraper.storage — data persistence sinks."""

from .base import AbstractStorage, StorageMeta
from .criteria import Criteria, FilterOperator, OrderDirection
from .repository import SQLServerRepository, get_portal_last_date
from .sqlserver_storage import SQLServerStorage

__all__ = [
    "AbstractStorage",
    "Criteria",
    "FilterOperator",
    "OrderDirection",
    "SQLServerRepository",
    "SQLServerStorage",
    "StorageMeta",
    "get_portal_last_date",
]
