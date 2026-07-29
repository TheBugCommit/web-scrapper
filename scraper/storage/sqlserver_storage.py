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
import re
import urllib.parse
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


def normalise_sqlserver_connection_string(
    conn_str: str, default_db: str = "Reporting_Test"
) -> str:
    """Convert any SQL Server connection string (SSMS, ADO.NET, or SQLAlchemy URL) into a bulletproof odbc_connect URL."""
    if "://" in conn_str and not conn_str.startswith("mssql"):
        return conn_str

    if "odbc_connect=" in conn_str:
        return conn_str

    server = "localhost"
    user = ""
    password = ""
    database = default_db
    driver = ""

    if "://" in conn_str:
        parsed = urllib.parse.urlsplit(conn_str)
        if parsed.username:
            user = urllib.parse.unquote(parsed.username)
        if parsed.password:
            password = urllib.parse.unquote(parsed.password)
        if parsed.hostname:
            server = urllib.parse.unquote(parsed.hostname)
            server = server.replace("%5C", "\\").replace("%5c", "\\")
        if parsed.path and len(parsed.path) > 1:
            database = parsed.path.lstrip("/")
        query = urllib.parse.parse_qs(parsed.query)
        if "driver" in query:
            driver = query["driver"][0].replace("+", " ")
    else:
        parts = [p.strip() for p in conn_str.split(";") if p.strip()]
        kv: dict[str, str] = {}
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k.strip().lower()] = v.strip()

        server = (
            kv.get("data source")
            or kv.get("server")
            or kv.get("addr")
            or "localhost"
        )
        user = kv.get("user id") or kv.get("uid") or kv.get("user") or ""
        password = kv.get("password") or kv.get("pwd") or ""
        database = (
            kv.get("initial catalog")
            or kv.get("database")
            or kv.get("catalog")
            or default_db
        )
        driver = kv.get("driver", "")
        if driver and driver.startswith("{") and driver.endswith("}"):
            driver = driver[1:-1]

    try:
        import pyodbc

        installed = pyodbc.drivers()
        if not driver or driver not in installed:
            for preferred in [
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
                "SQL Server Native Client 11.0",
                "SQL Server",
            ]:
                if preferred in installed:
                    driver = preferred
                    break
            if not driver and installed:
                driver = installed[0]
    except Exception:
        driver = driver or "ODBC Driver 18 for SQL Server"

    odbc_parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
    ]
    if user and password:
        odbc_parts.append(f"UID={user}")
        odbc_parts.append(f"PWD={password}")
    else:
        odbc_parts.append("Trusted_Connection=yes")

    odbc_parts.append("Encrypt=no")
    odbc_parts.append("TrustServerCertificate=yes")

    odbc_str = ";".join(odbc_parts) + ";"
    encoded = urllib.parse.quote_plus(odbc_str)
    return f"mssql+pyodbc:///?odbc_connect={encoded}"



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
        upsert_key: str | list[str] | None = None,
        auto_create_table: bool = True,
        schema_prefix: str = "dbo",
        extra_columns: dict[str, Any] | None = None,
    ) -> None:
        self._conn_str = normalise_sqlserver_connection_string(connection_string)
        self._table = table
        self._upsert_key = upsert_key
        self._auto_create = auto_create_table
        self._schema = schema_prefix
        self._extra_columns = extra_columns or {}
        self._engine: Engine | None = None
        self._table_created = False
        self._loop = asyncio.get_event_loop

    # ── Factory ───────────────────────────────────────────────────────────

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
        """Convert complex types to JSON strings and normalize timestamps for SQL Server DATETIMEOFFSET compatibility."""
        result: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                result[k] = json.dumps(v, ensure_ascii=False, default=str)
            elif v is None or isinstance(v, (int, float, bool)):
                result[k] = v
            elif isinstance(v, str):
                result[k] = re.sub(r"([+-]\d{2})$", r"\1:00", v.strip())
            else:
                result[k] = re.sub(r"([+-]\d{2})$", r"\1:00", str(v).strip())
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

            if self._has_upsert_key(row):
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
                if self._has_upsert_key(row):
                    self._merge(conn, full_table, row)
                else:
                    self._insert(conn, full_table, row)

    def _has_upsert_key(self, row: dict[str, Any]) -> bool:
        if not self._upsert_key:
            return False
        if isinstance(self._upsert_key, str):
            return self._upsert_key in row
        return all(k in row for k in self._upsert_key)

    def _insert(self, conn: Any, full_table: str, row: dict[str, Any]) -> None:
        cols = ", ".join(f"[{c}]" for c in row)
        params = ", ".join(f":{c}" for c in row)
        sql = text(f"INSERT INTO {full_table} ({cols}) VALUES ({params})")
        conn.execute(sql, row)

    def _merge(self, conn: Any, full_table: str, row: dict[str, Any]) -> None:
        """SQL Server MERGE (upsert) on the configured upsert key(s)."""
        keys = [self._upsert_key] if isinstance(self._upsert_key, str) else list(self._upsert_key or [])
        other_cols = [c for c in row if c not in keys]

        on_clause = " AND ".join(f"target.[{k}] = source.[{k}]" for k in keys)

        if not other_cols:
            # Only key column(s) — just insert if not exists
            where_clause = " AND ".join(f"[{k}] = :{k}" for k in keys)
            sql = text(
                f"IF NOT EXISTS (SELECT 1 FROM {full_table} WHERE {where_clause}) "
                f"INSERT INTO {full_table} ({', '.join(f'[{k}]' for k in keys)}) "
                f"VALUES ({', '.join(f':{k}' for k in keys)})"
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
            f"ON {on_clause} "
            f"WHEN MATCHED THEN UPDATE SET {update_set} "
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});"
        )
        conn.execute(text(sql_text), row)
