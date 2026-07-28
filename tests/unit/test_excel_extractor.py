"""Unit tests for ExcelExtractor and engine storage batching."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from scraper import ExcelExtractor
from scraper.backends.base import PageResponse


@pytest.mark.asyncio
async def test_excel_extractor() -> None:
    test_file = Path("downloads/test/Balfeg.xls")
    if not test_file.exists():
        pytest.skip("Test sample downloads/test/Balfeg.xls not found")

    extractor = ExcelExtractor(
        columns=["timestamp", "nivel_tanque_pct", "presion_bar"],
    )
    page = PageResponse(
        url="https://example.com/export.html",
        status_code=200,
        content="<html></html>",
        metadata={"downloads": [str(test_file)]},
    )

    data = await extractor.extract(page)
    assert "_rows" in data
    assert data["row_count"] > 0
    first = data["_rows"][0]
    assert "timestamp" in first
    assert first["timestamp"].endswith(":00")
    assert first["nivel_tanque_pct"] == 70.0
    assert first["presion_bar"] == 4.0
