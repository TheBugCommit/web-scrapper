"""
scraper.utils.excel
~~~~~~~~~~~~~~~~~~~
Excel reading and data cleaning utilities for extracting rows from scraped
spreadsheets (.xls, .xlsx) into database-ready dictionaries.

Usage::

    from scraper.utils.excel import read_excel_rows

    rows = read_excel_rows(
        "downloads/Balfeg.xls",
        columns=["timestamp", "nivel_tanque_pct", "presion_bar"],
    )
    await storage.save_many(rows)
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any


def read_excel_rows(
    filepath: str | Path,
    columns: list[str] | dict[str, str] | None = None,
    clean_comma_decimals: bool = True,
    exclude_clean_cols: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Read an Excel spreadsheet (.xls or .xlsx) and return a list of row dicts.

    Automatically handles Spanish/German comma decimals (e.g. ``"70,0"`` -> ``70.0``)
    and converts them to proper numeric types for database insertion.

    Parameters:
        filepath:             Path to the downloaded Excel file (.xls or .xlsx).
        columns:              Optional column mapping:
                              - If a list of names is given (e.g. ``["timestamp", "nivel", "presion"]``),
                                it renames columns sequentially from left to right.
                              - If a dict is given, it maps source headers to target column names.
        clean_comma_decimals: Whether to replace comma decimals (``','``) with dots (``'.'``)
                              and cast string numbers to floats/ints.
        exclude_clean_cols:   Column names to exempt from numeric conversion (e.g. primary keys / dates).
                              Defaults to ``["timestamp", "date", "fecha"]`` case-insensitively.

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

    # 2. Clean comma decimals and convert strings to float/int
    if clean_comma_decimals:
        default_excludes = {"timestamp", "date", "fecha", "id", "pk"}
        user_excludes = {col.lower() for col in (exclude_clean_cols or [])}
        all_excludes = default_excludes | user_excludes

        for col in df.columns:
            if str(col).lower() in all_excludes:
                continue

            series = df[col]
            # In pandas 3.0 strings have dtype 'str'/'string', while in older pandas they are 'object'
            if str(series.dtype).lower() in ("object", "str", "string", "string[python]", "string[pyarrow]"):
                # Check if values are strings with decimal comma, e.g. "70,0"
                cleaned = series.astype(str).str.strip().str.replace(",", ".", regex=False)
                df[col] = pd.to_numeric(cleaned, errors="coerce")

    df = df.where(pd.notnull(df), None)
    records = df.to_dict(orient="records")
    for row in records:
        for k, v in row.items():
            if isinstance(v, str):
                row[k] = re.sub(r"([+-]\d{2})$", r"\1:00", v.strip())
    return records
