"""
scraper.extractors.csv_extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Declarative data extractor that reads downloaded CSV spreadsheets (.csv)
and extracts clean rows ready for database persistence.

Usage in ScraperBuilder::

    session = (
        ScraperBuilder()
        .with_url(...)
        .with_interaction(...)  # downloads spreadsheet
        .with_extractor(
            CSVExtractor(
                columns=["nivel_cm", "udm_cm", "peso_kg", "udm_kg", "timestamp", "fuente"],
                tz="Europe/Madrid",
            )
        )
        .with_storage(portal.get_storage())
        .build()
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from scraper.extractors.base import AbstractExtractor
from scraper.utils.csv import read_csv_rows
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse

logger = get_logger(__name__)


class CSVExtractor(AbstractExtractor):
    """Extractor plugin that converts downloaded CSV files into structured rows.

    Parameters:
        columns:              Optional column mapping (sequential list or header dict).
        clean_comma_decimals: Replace Spanish comma decimals (e.g. ``"6.578,20"`` -> ``6578.20``).
        exclude_clean_cols:   Column names to exempt from numeric conversion (e.g. timestamps).
        tz:                   Timezone name for timestamp localization/conversion (e.g. ``"Europe/Madrid"``).
    """

    def __init__(
        self,
        columns: list[str] | dict[str, str] | None = None,
        clean_comma_decimals: bool = True,
        exclude_clean_cols: list[str] | None = None,
        tz: str | None = "Europe/Madrid",
    ) -> None:
        self.columns = columns
        self.clean_comma_decimals = clean_comma_decimals
        self.exclude_clean_cols = exclude_clean_cols
        self.tz = tz

    async def extract(self, page: "PageResponse") -> dict[str, Any]:
        """Extract table rows from any downloaded file in ``page.metadata["downloads"]``."""
        downloads = page.metadata.get("downloads", [])
        if not downloads:
            logger.debug("CSVExtractor: no downloaded files found in page.metadata")
            return {}

        csv_path = Path(downloads[0])
        logger.info("CSVExtractor: extracting rows from %s", csv_path)

        rows = read_csv_rows(
            csv_path,
            columns=self.columns,
            clean_comma_decimals=self.clean_comma_decimals,
            exclude_clean_cols=self.exclude_clean_cols,
            tz=self.tz,
        )
        logger.info("CSVExtractor: extracted %d clean records", len(rows))

        return {
            "_rows": rows,
            "row_count": len(rows),
            "spreadsheet_path": str(csv_path),
        }
