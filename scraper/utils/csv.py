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


def detect_file_encoding(path: Path) -> str:
    """Detect the character encoding of a file using BOM checking and charset_normalizer."""
    import codecs

    raw = path.read_bytes()[:4]
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if raw.startswith(codecs.BOM_UTF16_LE):
        return "utf-16le"
    if raw.startswith(codecs.BOM_UTF16_BE):
        return "utf-16be"

    try:
        import charset_normalizer
        match = charset_normalizer.from_path(path).best()
        if match and match.encoding:
            enc = match.encoding.lower().replace("_", "-")
            if enc == "utf-16-le":
                return "utf-16le"
            if enc == "utf-16-be":
                return "utf-16be"
            return enc
    except Exception:
        pass

    return "utf-8"


def _read_csv_df(path: Path) -> "pd.DataFrame":
    import pandas as pd

    encoding = detect_file_encoding(path)

    # Try automatic delimiter sniffing with the detected encoding
    try:
        df = pd.read_csv(path, sep=None, engine="python", encoding=encoding)
        if len(df.columns) > 1:
            return df
    except Exception:
        pass

    # Fallback to explicit separators if sniffing didn't split columns
    for sep in ("\t", ";", ","):
        try:
            df = pd.read_csv(path, sep=sep, encoding=encoding)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue

    return pd.read_csv(path, encoding=encoding)


def read_csv_rows(
    filepath: str | Path,
    columns: list[str] | dict[str, str] | None = None,
    clean_comma_decimals: bool = True,
    exclude_clean_cols: list[str] | None = None,
    tz: str | None = None,
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
        tz:                   Timezone name for timestamp localization/conversion, or
                               ``None`` (default) to leave timestamps timezone-naive.
                               Callers that need a specific timezone (e.g. ``"Europe/Madrid"``)
                               must pass it explicitly.

    Returns:
        A list of dictionary records ready for SQLServerStorage.save_many().
    """
    try:
        import pandas  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "pandas is required for read_csv_rows(). Install it with: pip install pandas"
        ) from exc

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path.resolve()}")

    df = _read_csv_df(path)

    from scraper.utils.converters import read_tabular_rows

    return read_tabular_rows(
        df,
        columns=columns,
        clean_comma_decimals=clean_comma_decimals,
        exclude_clean_cols=exclude_clean_cols,
        tz=tz,
    )
