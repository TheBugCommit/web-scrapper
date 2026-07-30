"""
scraper.storage.engine_factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shared factory for creating SQL Server SQLAlchemy engines.

Centralises engine creation to avoid duplication between
:class:`~scraper.storage.sqlserver_storage.SQLServerStorage` and
:class:`~scraper.storage.repository.SQLServerRepository`.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Engine


def create_sqlserver_engine(
    conn_str: str,
    pool_size: int = 5,
    max_overflow: int = 10,
    echo: bool = False,
) -> Engine:
    """Create a SQL Server SQLAlchemy engine with sensible defaults.

    Parameters:
        conn_str:     Normalised SQLAlchemy connection URL (``mssql+pyodbc://...``).
        pool_size:    Number of connections to keep in the pool.
        max_overflow: Max connections above *pool_size* allowed temporarily.
        echo:         Log all SQL statements (useful for debugging).

    Returns:
        A configured :class:`sqlalchemy.engine.Engine` instance.
    """
    return sa.create_engine(
        conn_str,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
    )
