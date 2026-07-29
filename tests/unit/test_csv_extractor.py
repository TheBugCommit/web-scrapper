"""Unit tests for CSVExtractor."""

from __future__ import annotations

from pathlib import Path

import pytest
from scraper import CSVExtractor
from scraper.backends.base import PageResponse


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "readings.csv"
    content = (
        "Valor\tUDM\tValor\tUDM\tFecha/Hora\tFuente\n"
        "281\tCM\t6.578,20\tKG\t29/07/2026 8:38\tTelemetría\n"
        "282\tCM\t6.601,60\tKG\t29/07/2026 7:00\tTelemetría\n"
    )
    csv_path.write_text(content, encoding="utf-8-sig")
    return csv_path


@pytest.mark.asyncio
async def test_csv_extractor(sample_csv: Path) -> None:
    extractor = CSVExtractor(
        columns=["nivel_cm", "udm_cm", "peso_kg", "udm_kg", "timestamp", "fuente"],
        tz="Europe/Madrid",
    )
    page = PageResponse(
        url="https://example.com/export.html",
        status_code=200,
        content="<html></html>",
        metadata={"downloads": [str(sample_csv)]},
    )

    data = await extractor.extract(page)
    assert "_rows" in data
    assert data["row_count"] == 2
    first = data["_rows"][0]
    assert first["nivel_cm"] == 281.0
    assert first["udm_cm"] == "CM"
    assert first["peso_kg"] == 6578.20
    assert first["udm_kg"] == "KG"
    assert first["timestamp"] == "2026-07-29 08:38:00+02:00"
    assert first["fuente"] == "Telemetría"
