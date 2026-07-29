"""
scraper.storage.repository
~~~~~~~~~~~~~~~~~~~~~~~~~~
Modular database repository that queries SQL Server using the declarative
Criteria Pattern.

Can be used outside the scraper engine to inspect tables, check existence,
and retrieve dynamic parameters such as the last scraped date.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from functools import partial
from typing import Any, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.engine import Engine

from scraper.storage.criteria import Criteria, compile_criteria_to_sqlserver
from scraper.storage.sqlserver_storage import normalise_sqlserver_connection_string
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from typing import Protocol

    class _PortalLike(Protocol):
        db_schema: str

logger = get_logger(__name__)


class SQLServerRepository:
    """Async repository for querying SQL Server tables via the Criteria pattern.

    Construct instances using one of the factory class-methods:
    - :meth:`from_env`: read connection string from ``SCRAPER_DB_CONNECTION_STRING``
    - :meth:`from_portal`: derive schema from a PortalConfig object

    Example usage::

        async with SQLServerRepository.from_env() as repo:
            last_date = await repo.get_last_date(
                table="Telemetria_Tanque_N",
                date_column="timestamp",
                schema="dbo",
                default_date=date(2024, 5, 1),
            )
    """

    def __init__(self, connection_string: str, default_schema: str = "dbo") -> None:
        self._raw_conn_str = connection_string
        self._conn_str = normalise_sqlserver_connection_string(connection_string)
        self._default_schema = default_schema
        self._engine: Engine | None = None

    @classmethod
    def from_portal(cls, portal: "_PortalLike", connection_string: str) -> "SQLServerRepository":
        """Instantiate a repository from a portal config object and explicit connection string."""
        schema = getattr(portal, "db_schema", "dbo") or "dbo"
        if not connection_string:
            raise ValueError("connection_string is required to instantiate SQLServerRepository.")
        return cls(connection_string=connection_string, default_schema=schema)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def open(self) -> None:
        """Connect the underlying SQLAlchemy engine pool."""
        loop = asyncio.get_event_loop()
        self._engine = await loop.run_in_executor(
            None,
            partial(
                sa.create_engine,
                self._conn_str,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                echo=False,
            ),
        )
        logger.debug("SQLServerRepository: engine opened")

    async def close(self) -> None:
        """Dispose the engine pool."""
        if self._engine is not None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._engine.dispose)
            self._engine = None
            logger.debug("SQLServerRepository: engine disposed")

    async def __aenter__(self) -> "SQLServerRepository":
        await self.open()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _engine_or_raise(self) -> Engine:
        if self._engine is None:
            raise RuntimeError(
                "Repository is not open. Call open() or use as an async context manager: "
                "async with repo: ..."
            )
        return self._engine

    # ── Criteria Execution ────────────────────────────────────────────────

    def _sync_execute_criteria(self, criteria: Criteria) -> list[dict[str, Any]]:
        engine = self._engine_or_raise()
        sql_str, params = compile_criteria_to_sqlserver(criteria)
        logger.debug("SQLServerRepository execute: %s | params=%s", sql_str, params)

        with engine.connect() as conn:
            result = conn.execute(text(sql_str), params)
            rows = result.mappings().fetchall()
            return [dict(r) for r in rows]

    async def find(self, criteria: Criteria) -> list[dict[str, Any]]:
        """Execute a Criteria specification and return a list of matching row dicts."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._sync_execute_criteria, criteria))

    async def find_one(self, criteria: Criteria) -> dict[str, Any] | None:
        """Execute a Criteria specification and return the first matching row, or None."""
        rows = await self.find(criteria)
        return rows[0] if rows else None

    # ── High-Level Domain Helpers ─────────────────────────────────────────

    async def table_exists(self, table: str, schema: str = "dbo") -> bool:
        """Check if a table exists in the SQL Server database using the Criteria pattern."""
        criteria = (
            Criteria.for_table("TABLES", schema="INFORMATION_SCHEMA")
            .where("TABLE_SCHEMA", "=", schema)
            .where("TABLE_NAME", "=", table)
            .take(1)
        )
        row = await self.find_one(criteria)
        return row is not None

    async def get_last_date(
        self,
        table: str,
        date_column: str = "timestamp",
        schema: str = "dbo",
        default_date: date = date(2024, 5, 1),
    ) -> date:
        """Query the last (maximum) date from a portal table using the Criteria pattern.

        If the table does not exist or has no records, returns ``default_date``
        (defaults to ``2024-05-01``).

        Parameters:
            table:        Target table name.
            date_column:  Column name containing dates or timestamps (default: "timestamp").
            schema:       Database schema (default: "dbo").
            default_date: Fallback date if table does not exist or is empty (default: 01/05/2024).
        """
        exists = await self.table_exists(table, schema=schema)
        if not exists:
            logger.info(
                "Table [%s].[%s] does not exist; returning default_date=%s",
                schema,
                table,
                default_date.isoformat(),
            )
            return default_date

        criteria = (
            Criteria.for_table(table, schema=schema)
            .select_max(date_column, alias="last_val")
        )
        row = await self.find_one(criteria)
        if not row or row.get("last_val") is None:
            logger.info(
                "Table [%s].[%s] is empty; returning default_date=%s",
                schema,
                table,
                default_date.isoformat(),
            )
            return default_date

        val = row["last_val"]
        return self._parse_date_value(val, default_date)

    @staticmethod
    def _parse_date_value(val: Any, default_date: date) -> date:
        """Safely convert database result to a Python date object."""
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            clean = val.strip()
            if len(clean) >= 10:
                try:
                    return date.fromisoformat(clean[:10])
                except ValueError:
                    pass
        logger.warning("Unable to parse date value %r; falling back to default_date", val)
        return default_date


async def get_portal_last_date(
    portal: "_PortalLike",
    connection_string: str,
    date_column: str = "timestamp",
    default_date: date = date(2024, 5, 1),
) -> date:
    """Helper that queries the last scraped date for a portal outside the scraper engine.

    Uses the Criteria Pattern via SQLServerRepository.
    If the portal's target table does not exist or is empty, returns ``default_date``
    (01/05/2024 by default).
    """
    table = getattr(portal, "db_table", "scraped_data") or "scraped_data"
    schema = getattr(portal, "db_schema", "dbo") or "dbo"

    async with SQLServerRepository.from_portal(portal, connection_string=connection_string) as repo:
        return await repo.get_last_date(
            table=table,
            date_column=date_column,
            schema=schema,
            default_date=default_date,
        )
