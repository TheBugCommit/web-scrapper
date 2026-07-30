"""
scraper.extractors.excel_extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Declarative data extractor that reads downloaded Excel spreadsheets (.xls, .xlsx)
and extracts clean rows ready for database persistence.

Usage in ScraperBuilder::

    session = (
        ScraperBuilder()
        .with_url(...)
        .with_interaction(...)  # downloads spreadsheet
        .with_extractor(
            ExcelExtractor(columns=["timestamp", "nivel_tanque_pct", "presion_bar"])
        )
        .with_storage(portal.get_storage(connection_string))
        .build()
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from scraper.extractors.base import AbstractExtractor
from scraper.utils.excel import read_excel_rows
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse

logger = get_logger(__name__)


class ExcelExtractor(AbstractExtractor):
    """Extractor plugin that converts downloaded spreadsheets into structured rows.

    Parameters:
        columns:              Optional column mapping (sequential list or header dict).
        clean_comma_decimals: Replace Spanish/German comma decimals (e.g. ``"70,0"`` -> ``70.0``).
        exclude_clean_cols:   Column names to exempt from numeric conversion (e.g. timestamps).
        tz:                   Timezone name for timestamp localization/conversion
                              (e.g. ``"Europe/Madrid"``), or ``None`` (default) to leave
                              timestamps timezone-naive.
    """

    def __init__(
        self,
        columns: list[str] | dict[str, str] | None = None,
        clean_comma_decimals: bool = True,
        exclude_clean_cols: list[str] | None = None,
        tz: str | None = None,
    ) -> None:
        self.columns = columns
        self.clean_comma_decimals = clean_comma_decimals
        self.exclude_clean_cols = exclude_clean_cols
        self.tz = tz

    async def extract(self, page: "PageResponse") -> dict[str, Any]:
        """Extract table rows from any Excel file in ``page.metadata["downloads"]``."""
        downloads = page.metadata.get("downloads", [])
        if not downloads:
            logger.debug("ExcelExtractor: no downloaded files found in page.metadata")
            return {}

        xls_path = Path(downloads[0])
        logger.info("ExcelExtractor: extracting rows from %s", xls_path)

        rows = read_excel_rows(
            xls_path,
            columns=self.columns,
            clean_comma_decimals=self.clean_comma_decimals,
            exclude_clean_cols=self.exclude_clean_cols,
            tz=self.tz,
        )
        logger.info("ExcelExtractor: extracted %d clean records", len(rows))

        return {
            "_rows": rows,
            "row_count": len(rows),
            "spreadsheet_path": str(xls_path),
        }
