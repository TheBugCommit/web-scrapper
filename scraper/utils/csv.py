"""
scraper.utils.csv
~~~~~~~~~~~~~~~~~
CSV reading and data cleaning utilities for extracting rows from scraped
CSV spreadsheets into database-ready dictionaries.

Supports automatic delimiter sniffing (semicolon, tab, comma) and automatic
detection of numeric columns and datetime columns without relying on hardcoded
column names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def _read_csv_df(path: Path) -> "pd.DataFrame":
    import pandas as pd

    # Try automatic delimiter sniffing with common European/UTF encodings
    for enc in ("utf-8-sig", "utf-8", "latin-1", "iso-8859-1"):
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding=enc)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue

    # Fallback to explicit separators if sniffing didn't split columns
    for sep in ("\t", ";", ","):
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue

    # Default fallback
    return pd.read_csv(path)


def read_csv_rows(
    filepath: str | Path,
    columns: list[str] | dict[str, str] | None = None,
    clean_comma_decimals: bool = True,
    exclude_clean_cols: list[str] | None = None,
    tz: str | None = "Europe/Madrid",
) -> list[dict[str, Any]]:
    """Read a CSV file and return a list of row dicts.

    Automatically detects date/time columns (converting them to SQL Server
    DATETIMEOFFSET compatible format) and Spanish comma decimals without
    relying on hardcoded column names.

    Parameters:
        filepath:             Path to the downloaded CSV file.
        columns:              Optional column mapping (list by position or dict by header name).
        clean_comma_decimals: Whether to clean thousands dots and comma decimals.
        exclude_clean_cols:   Column names to exempt from numeric conversion.
        tz:                   Timezone name for timestamp localization/conversion (default ``"Europe/Madrid"``).

    Returns:
        A list of dictionary records ready for SQLServerStorage.save_many().
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas is required for read_csv_rows(). Install it with: pip install pandas"
        ) from exc

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path.resolve()}")

    df = _read_csv_df(path)

    # 1. Map columns if requested
    if isinstance(columns, list):
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
        if str(col).lower() in user_excludes:
            continue

        series = df[col]
        if is_datetime_series(series):
            df[col] = convert_datetime_series_to_iso(series, tz=tz)
        elif clean_comma_decimals and is_numeric_string_series(series):
            df[col] = clean_comma_decimal_series(series)

    df = df.where(pd.notnull(df), None)
    return [
        {str(k): v for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]
