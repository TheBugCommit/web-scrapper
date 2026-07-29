"""
scraper.utils.converters
~~~~~~~~~~~~~~~~~~~~~~~~
Generic column type detection and data conversion helpers for tabular data
(CSV and Excel readers).

Detects datetime and numeric columns dynamically by inspecting values rather
than relying on hardcoded column names.
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def _parse_dates_quietly(series: "pd.Series") -> "pd.Series":
    import pandas as pd

    try:
        return pd.to_datetime(series, format="mixed", dayfirst=True, errors="coerce")
    except (TypeError, ValueError):
        return pd.to_datetime(series, dayfirst=True, errors="coerce")


def is_datetime_series(series: "pd.Series") -> bool:
    """Detect if a pandas Series represents dates/timestamps without relying on column names."""
    import pandas as pd

    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        non_null = series.dropna().astype(str).str.strip()
        if non_null.empty:
            return False
        # Must contain date/time separators with digits (e.g. DD/MM/YYYY, YYYY-MM-DD, HH:MM, ISO format)
        date_pattern = re.compile(
            r"(\d{1,4}[/-]\d{1,2}[/-]\d{1,4}|\d{1,2}:\d{2}(:\d{2})?)"
        )
        sample = non_null.head(20)
        if all(bool(date_pattern.search(str(val))) for val in sample):
            parsed = _parse_dates_quietly(sample)
            return bool(parsed.notna().all())
    return False


def is_numeric_string_series(series: "pd.Series") -> bool:
    """Detect if a string/object pandas Series contains formatted numbers (e.g. ``'6.578,20'``)."""
    import pandas as pd

    if pd.api.types.is_numeric_dtype(series):
        return True
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        non_null = series.dropna().astype(str).str.strip()
        if non_null.empty:
            return False
        # Pattern matches integer or decimal numbers with optional dot thousands and comma/dot decimals
        num_pattern = re.compile(r"^[+-]?(?:\d{1,3}(?:\.\d{3})*|\d+)(?:[.,]\d+)?$")
        sample = non_null.head(20)
        return all(bool(num_pattern.match(str(val))) for val in sample)
    return False


def convert_datetime_series_to_iso(
    series: "pd.Series",
    tz: str | None = "Europe/Madrid",
) -> "pd.Series":
    """Parse a datetime Series and format it as an ISO 8601 string with timezone offset."""
    import pandas as pd

    parsed = _parse_dates_quietly(series)

    def _to_iso_tz(val: Any) -> Any:
        if pd.isna(val) or val is None:
            return None
        try:
            if tz:
                if getattr(val, "tz", None) is None:
                    localized = val.tz_localize(tz)
                else:
                    localized = val.tz_convert(tz)
                res = localized.isoformat(sep=" ")
            else:
                res = val.isoformat(sep=" ")
            return re.sub(r"([+-]\d{2})$", r"\1:00", res.strip())
        except Exception:
            return str(val)

    res = parsed.apply(_to_iso_tz)
    if isinstance(res, pd.Series):
        return res
    return pd.Series(res, index=series.index)


def clean_comma_decimal_series(series: "pd.Series") -> "pd.Series":
    """Clean Spanish/European formatted numbers (e.g. ``'6.578,20'`` -> float ``6578.20``)."""
    import pandas as pd

    if str(series.dtype).lower() in ("object", "str", "string", "string[python]", "string[pyarrow]"):
        cleaned = (
            series.astype(str)
            .str.strip()
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        res = pd.to_numeric(cleaned, errors="coerce")
        if isinstance(res, pd.Series):
            return res
        return pd.Series(res, index=series.index)
    return series
