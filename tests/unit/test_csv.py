"""Unit tests for scraper.utils.csv and dynamic column type detection."""

from __future__ import annotations

from pathlib import Path

import pytest
from scraper.utils.csv import read_csv_rows


@pytest.fixture
def sample_carburos_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "carburos_readings.csv"
    content = (
        "Valor\tUDM\tValor\tUDM\tFecha/Hora\tFuente\n"
        "281\tCM\t6.578,20\tKG\t29/07/2026 8:38\tTelemetría\n"
        "282\tCM\t6.601,60\tKG\t29/07/2026 7:00\tTelemetría\n"
    )
    csv_path.write_text(content, encoding="utf-8-sig")
    return csv_path


@pytest.fixture
def sample_carburos_semicolon_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "carburos_readings_semi.csv"
    content = (
        "Valor;UDM;Valor;UDM;Fecha/Hora;Fuente\n"
        "281;CM;6.578,20;KG;29/07/2026 8:38;Telemetría\n"
        "282;CM;6.601,60;KG;29/07/2026 7:00;Telemetría\n"
    )
    csv_path.write_text(content, encoding="utf-8-sig")
    return csv_path


def test_dynamic_type_detection() -> None:
    import pandas as pd
    from scraper.utils.converters import is_datetime_series, is_numeric_string_series

    s_date = pd.Series(["29/07/2026 8:38", "29/07/2026 7:00"])
    s_num = pd.Series(["6.578,20", "281"])
    s_text = pd.Series(["CM", "KG", "Telemetría"])

    assert is_datetime_series(s_date) is True
    assert is_datetime_series(s_num) is False
    assert is_datetime_series(s_text) is False

    assert is_numeric_string_series(s_num) is True
    assert is_numeric_string_series(s_text) is False
    assert is_numeric_string_series(s_date) is False


def test_read_csv_rows_carburos_tab_separated(sample_carburos_csv: Path) -> None:
    rows = read_csv_rows(
        sample_carburos_csv,
        columns=["nivel_cm", "udm_cm", "peso_kg", "udm_kg", "timestamp", "fuente"],
        tz="Europe/Madrid",
    )
    assert len(rows) == 2

    first = rows[0]
    assert first["nivel_cm"] == 281.0
    assert first["udm_cm"] == "CM"
    assert first["peso_kg"] == 6578.20
    assert first["udm_kg"] == "KG"
    assert first["timestamp"] == "2026-07-29 08:38:00+02:00"
    assert first["fuente"] == "Telemetría"

    second = rows[1]
    assert second["nivel_cm"] == 282.0
    assert second["peso_kg"] == 6601.60
    assert second["timestamp"] == "2026-07-29 07:00:00+02:00"


def test_read_csv_rows_carburos_semicolon_separated(
    sample_carburos_semicolon_csv: Path,
) -> None:
    rows = read_csv_rows(
        sample_carburos_semicolon_csv,
        columns=["nivel_cm", "udm_cm", "peso_kg", "udm_kg", "timestamp", "fuente"],
        tz="Europe/Madrid",
    )
    assert len(rows) == 2
    assert rows[0]["peso_kg"] == 6578.20
    assert rows[0]["timestamp"] == "2026-07-29 08:38:00+02:00"
