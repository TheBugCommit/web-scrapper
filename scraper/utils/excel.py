"""
scraper.utils.excel
~~~~~~~~~~~~~~~~~~~
Excel reading and data cleaning utilities for extracting rows from scraped
spreadsheets (.xls, .xlsx) into database-ready dictionaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_excel_rows(
    filepath: str | Path,
    columns: list[str] | dict[str, str] | None = None,
    clean_comma_decimals: bool = True,
    exclude_clean_cols: list[str] | None = None,
    tz: str | None = None,
) -> list[dict[str, Any]]:
    """Read an Excel spreadsheet (.xls or .xlsx) and return a list of row dicts.

    Automatically detects date/time columns (converting them to SQL Server
    DATETIMEOFFSET compatible format) and Spanish/German comma decimals
    without relying on hardcoded column names.

    Parameters:
        filepath:             Path to the downloaded Excel file (.xls or .xlsx).
        columns:              Optional column mapping:
                              - If a list of names is given (e.g. ``["timestamp", "nivel", "presion"]``),
                                it renames columns sequentially from left to right.
                              - If a dict is given, it maps source headers to target column names.
        clean_comma_decimals: Whether to replace comma decimals (``','``) with dots (``'.'``)
                              and cast string numbers to floats/ints.
        exclude_clean_cols:   Column names to exempt from numeric conversion.
        tz:                   Timezone name for timestamp localization/conversion, or
                               ``None`` (default) to leave timestamps timezone-naive.
                               Callers that need a specific timezone (e.g. ``"Europe/Madrid"``)
                               must pass it explicitly.

    Returns:
        A list of dictionary records ready for SQLServerStorage.save_many().

    Raises:
        ImportError: If pandas, xlrd, or openpyxl are not installed.
        FileNotFoundError: If the specified file does not exist.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas, xlrd, and openpyxl are required for read_excel_rows(). "
            "Install them with: pip install pandas xlrd openpyxl"
        ) from exc

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path.resolve()}")

    df = pd.read_excel(path)

    from scraper.utils.converters import read_tabular_rows

    return read_tabular_rows(
        df,
        columns=columns,
        clean_comma_decimals=clean_comma_decimals,
        exclude_clean_cols=exclude_clean_cols,
        tz=tz,
    )
