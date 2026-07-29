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
    tz: str | None = "Europe/Madrid",
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
        tz:                   Timezone name for timestamp localization/conversion (default ``"Europe/Madrid"``).

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

    # 1. Map columns if requested
    if isinstance(columns, list):
        # Rename by position up to len(columns)
        num_cols = min(len(columns), len(df.columns))
        rename_map = {df.columns[i]: columns[i] for i in range(num_cols)}
        df = df.rename(columns=rename_map)
    elif isinstance(columns, dict):
        df = df.rename(columns=columns)

    user_excludes = {col.lower() for col in (exclude_clean_cols or [])}

    # 2. Automatically detect and convert column types (dates/timestamps vs numeric strings)
    from scraper.utils.converters import (
        clean_comma_decimal_series,
        convert_datetime_series_to_iso,
        is_datetime_series,
        is_numeric_string_series,
    )

    for col in df.columns:
        if col.lower() in user_excludes:
            continue

        series = df[col]
        if is_datetime_series(series):
            df[col] = convert_datetime_series_to_iso(series, tz=tz)
        elif clean_comma_decimals and is_numeric_string_series(series):
            df[col] = clean_comma_decimal_series(series)

    import math

    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        clean_row: dict[str, Any] = {}
        for k, v in row.items():
            if v is None or pd.isna(v) or (isinstance(v, float) and math.isnan(v)):
                clean_row[str(k)] = None
            else:
                clean_row[str(k)] = v
        records.append(clean_row)
    return records
