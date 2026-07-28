"""scraper.storage — data persistence sinks."""

from .base import AbstractStorage
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
    "get_portal_last_date",
]
