"""Unit tests for scraper.utils.excel."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from scraper.utils.excel import read_excel_rows


def test_read_excel_rows_balfeg(tmp_path: Path) -> None:
    test_file = Path("downloads/test/Balfeg.xls")
    if not test_file.exists():
        pytest.skip("Test sample downloads/test/Balfeg.xls not found")

    rows = read_excel_rows(
        test_file,
        columns=["timestamp", "nivel_tanque_pct", "presion_bar"],
    )
    assert len(rows) > 0
    first = rows[0]
    assert "timestamp" in first
    assert "nivel_tanque_pct" in first
    assert "presion_bar" in first
    assert isinstance(first["nivel_tanque_pct"], float)
    assert isinstance(first["presion_bar"], float)
    # Ensure comma was converted to dot
    assert first["nivel_tanque_pct"] == 24.0
    assert first["presion_bar"] == 5.76
