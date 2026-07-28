"""
scraper.storage.sqlserver_storage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SQL Server storage sink powered by SQLAlchemy (async + pyodbc).

Features
--------
- **Auto-create table**: if the target table does not exist, creates it
  dynamically using the keys of the first inserted row as column names.
- **Upsert strategy**: configurable — ``INSERT`` only, or ``MERGE`` (upsert)
  on a primary key column.
- **Async execution**: all DB I/O runs in a thread-pool executor so it does
  not block the asyncio event loop.
- **Environment-driven config**: call :meth:`from_env` to read all settings
  from environment variables / ``.env`` file.

Connection string format (``SCRAPER_DB_CONNECTION_STRING``)::

    mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server
    mssql+pyodbc://server/db?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes
"""

from __future__ import annotations

import asyncio
import json
import os
from functools import partial
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.engine import Engine

from scraper.storage.base import AbstractStorage
from scraper.utils.logging import get_logger

logger = get_logger(__name__)

# SQL Server types used for auto-created columns
_TYPE_MAP: dict[type, str] = {
    int: "BIGINT",
    float: "FLOAT",
    bool: "BIT",
    str: "NVARCHAR(MAX)",
    list: "NVARCHAR(MAX)",  # serialised as JSON string
    dict: "NVARCHAR(MAX)",
}

_DEFAULT_COL_TYPE = "NVARCHAR(MAX)"


class SQLServerStorage(AbstractStorage):
    """Async SQL Server storage sink.

    Parameters:
        connection_string:  SQLAlchemy connection string for SQL Server.
        table:              Target table name (schema-qualified names are supported,
                            e.g. ``"dbo.scraped_data"``).
        upsert_key:         Column name to use as the upsert key for MERGE
                            statements.  Set to *None* to always INSERT.
        auto_create_table:  Automatically create the table if it does not exist.
        schema_prefix:      Optional schema prefix (e.g. ``"dbo"``).
        extra_columns:      Static extra columns added to every row
                            (e.g. ``{"source": "portal_x"}``).
    """

    def __init__(
        self,
        connection_string: str,
        table: str,
        upsert_key: str | None = None,
        auto_create_table: bool = True,
        schema_prefix: str = "dbo",
        extra_columns: dict[str, Any] | None = None,
    ) -> None:
        self._conn_str = connection_string
        self._table = table
        self._upsert_key = upsert_key
        self._auto_create = auto_create_table
        self._schema = schema_prefix
        self._extra_columns = extra_columns or {}
        self._engine: Engine | None = None
        self._table_created = False
        self._loop = asyncio.get_event_loop

    # ── Factory ───────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "SQLServerStorage":
        """Instantiate from environment variables.

        Reads::
            SCRAPER_DB_CONNECTION_STRING  (required)
            SCRAPER_DB_TABLE              (default: scraped_data)
            SCRAPER_DB_UPSERT_KEY         (optional)
            SCRAPER_DB_SCHEMA             (default: dbo)
        """
        conn = os.environ.get("SCRAPER_DB_CONNECTION_STRING", "")
        if not conn:
            raise ValueError(
                "SCRAPER_DB_CONNECTION_STRING environment variable is not set. "
                "Copy .env.example to .env and fill in the value."
            )
        return cls(
            connection_string=conn,
            table=os.environ.get("SCRAPER_DB_TABLE", "scraped_data"),
            upsert_key=os.environ.get("SCRAPER_DB_UPSERT_KEY") or None,
            schema_prefix=os.environ.get("SCRAPER_DB_SCHEMA", "dbo"),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def open(self) -> None:
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
        logger.debug("SQLServerStorage: engine connected to %s", self._table)

    async def close(self) -> None:
        if self._engine is not None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._engine.dispose)
            self._engine = None
        logger.debug("SQLServerStorage: engine disposed")

    # ── Public API ────────────────────────────────────────────────────────

    async def save(self, data: dict[str, Any]) -> None:
        """Insert (or upsert) a single row into the target table."""
        row = {**self._extra_columns, **data}
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._sync_save, row))

    async def save_many(self, rows: list[dict[str, Any]]) -> None:
        """Bulk-insert multiple rows in a single transaction."""
        if not rows:
            return
        prepared = [{**self._extra_columns, **r} for r in rows]
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._sync_save_many, prepared))

    # ── Synchronous helpers (run in thread pool) ──────────────────────────

    def _engine_or_raise(self) -> Engine:
        if self._engine is None:
            raise RuntimeError(
                "Storage is not open.  Use it as an async context manager or "
                "call ScraperBuilder.with_storage() before running the engine."
            )
        return self._engine

    def _ensure_table(self, conn: Any, row: dict[str, Any]) -> None:
        """Create the table if it does not exist, based on the row schema."""
        if self._table_created:
            return

        # Parse schema + table name
        parts = self._table.split(".")
        schema = parts[0] if len(parts) > 1 else self._schema
        tname = parts[-1]

        # Check existence
        check_sql = text(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table"
        )
        exists = conn.execute(check_sql, {"schema": schema, "table": tname}).fetchone()
        if exists:
            self._table_created = True
            return

        # Build CREATE TABLE
        col_defs = ["[_id] BIGINT IDENTITY(1,1) PRIMARY KEY"]
        for col, val in row.items():
            sql_type = _TYPE_MAP.get(type(val), _DEFAULT_COL_TYPE)
            safe_col = col.replace("]", "]]")
            col_defs.append(f"[{safe_col}] {sql_type} NULL")

        full_table = f"[{schema}].[{tname}]"
        ddl = f"CREATE TABLE {full_table} ({', '.join(col_defs)})"
        logger.info("SQLServerStorage: creating table %s", full_table)
        conn.execute(text(ddl))
        conn.commit()
        self._table_created = True

    def _serialise_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Convert complex types to JSON strings for SQL Server compatibility."""
        result: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                result[k] = json.dumps(v, ensure_ascii=False, default=str)
            elif v is None or isinstance(v, (str, int, float, bool)):
                result[k] = v
            else:
                result[k] = str(v)
        return result

    def _sync_save(self, row: dict[str, Any]) -> None:
        row = self._serialise_row(row)
        engine = self._engine_or_raise()
        parts = self._table.split(".")
        schema = parts[0] if len(parts) > 1 else self._schema
        tname = parts[-1]
        full_table = f"[{schema}].[{tname}]"

        with engine.begin() as conn:
            self._ensure_table(conn, row)

            if self._upsert_key and self._upsert_key in row:
                self._merge(conn, full_table, row)
            else:
                self._insert(conn, full_table, row)

    def _sync_save_many(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        rows = [self._serialise_row(r) for r in rows]
        engine = self._engine_or_raise()
        parts = self._table.split(".")
        schema = parts[0] if len(parts) > 1 else self._schema
        tname = parts[-1]
        full_table = f"[{schema}].[{tname}]"

        with engine.begin() as conn:
            self._ensure_table(conn, rows[0])
            for row in rows:
                if self._upsert_key and self._upsert_key in row:
                    self._merge(conn, full_table, row)
                else:
                    self._insert(conn, full_table, row)

    def _insert(self, conn: Any, full_table: str, row: dict[str, Any]) -> None:
        cols = ", ".join(f"[{c}]" for c in row)
        params = ", ".join(f":{c}" for c in row)
        sql = text(f"INSERT INTO {full_table} ({cols}) VALUES ({params})")
        conn.execute(sql, row)

    def _merge(self, conn: Any, full_table: str, row: dict[str, Any]) -> None:
        """SQL Server MERGE (upsert) on the configured upsert key."""
        key = self._upsert_key
        other_cols = [c for c in row if c != key]

        if not other_cols:
            # Only key column — just insert if not exists
            sql = text(
                f"IF NOT EXISTS (SELECT 1 FROM {full_table} WHERE [{key}] = :{key}) "
                f"INSERT INTO {full_table} ([{key}]) VALUES (:{key})"
            )
            conn.execute(sql, row)
            return

        update_set = ", ".join(f"target.[{c}] = source.[{c}]" for c in other_cols)
        insert_cols = ", ".join(f"[{c}]" for c in row)
        insert_vals = ", ".join(f"source.[{c}]" for c in row)
        source_cols = ", ".join(f":{c} AS [{c}]" for c in row)

        sql_text = (
            f"MERGE {full_table} AS target "
            f"USING (SELECT {source_cols}) AS source "
            f"ON target.[{key}] = source.[{key}] "
            f"WHEN MATCHED THEN UPDATE SET {update_set} "
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});"
        )
        conn.execute(text(sql_text), row)
