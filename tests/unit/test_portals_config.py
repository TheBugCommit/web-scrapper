"""Unit tests for portals.config (PortalRegistry, PortalConfig).

Covers the previously-untested config-loading layer: YAML merge, the new
`db_default_start_date` field, and the explicit-connection_string contract
introduced when PortalConfig stopped reading os.environ internally.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

CONFIG_YAML = """
portals:
  testportal:
    name: "Test Portal"
    portal_url: "https://example.com"
    login_url: "https://example.com/login"
    username_field: "user"
    password_field: "pass"
    success_selector: ".dashboard"
    headless: true
    db_table: "TestTable"
    db_schema: "dbo"
    db_upsert_key: "timestamp"
    db_default_start_date: "2024-05-01"
"""

CREDENTIALS_YAML = """
testportal:
  username: "myuser"
  password: "mypass"
"""


@pytest.fixture
def portal_yaml_files(tmp_path: Path) -> tuple[Path, Path]:
    config_path = tmp_path / "portals.yml"
    creds_path = tmp_path / "portals_credentials.yml"
    config_path.write_text(CONFIG_YAML, encoding="utf-8")
    creds_path.write_text(CREDENTIALS_YAML, encoding="utf-8")
    return config_path, creds_path


def test_portal_registry_load_parses_db_default_start_date(
    portal_yaml_files: tuple[Path, Path],
) -> None:
    from portals.config.registry import PortalRegistry

    config_path, creds_path = portal_yaml_files
    registry = PortalRegistry.load(config_path=config_path, credentials_path=creds_path)

    portal = registry.get("testportal")
    assert portal.username == "myuser"
    assert portal.password == "mypass"
    assert portal.db_table == "TestTable"
    assert portal.db_default_start_date == date(2024, 5, 1)


def test_portal_registry_get_unknown_key_raises(
    portal_yaml_files: tuple[Path, Path],
) -> None:
    from portals.config.registry import PortalRegistry

    config_path, creds_path = portal_yaml_files
    registry = PortalRegistry.load(config_path=config_path, credentials_path=creds_path)

    with pytest.raises(KeyError):
        registry.get("does_not_exist")


def test_portal_registry_warns_on_missing_credentials(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from portals.config.registry import PortalRegistry

    config_path = tmp_path / "portals.yml"
    creds_path = tmp_path / "portals_credentials.yml"
    config_path.write_text(CONFIG_YAML, encoding="utf-8")
    creds_path.write_text("{}", encoding="utf-8")

    with caplog.at_level("WARNING"):
        PortalRegistry.load(config_path=config_path, credentials_path=creds_path)

    assert any("missing username/password" in rec.message for rec in caplog.records)


def _make_portal_config(**overrides: object):
    from portals.config.models import PortalConfig

    defaults: dict[str, object] = dict(
        key="testportal",
        name="Test Portal",
        portal_url="https://example.com",
        login_url="https://example.com/login",
        username="myuser",
        password="mypass",
        db_table="TestTable",
        db_schema="dbo",
        db_upsert_key="timestamp",
        db_default_start_date=date(2024, 5, 1),
    )
    defaults.update(overrides)
    return PortalConfig(**defaults)


def test_portal_config_get_storage_rejects_empty_connection_string() -> None:
    portal = _make_portal_config()

    with pytest.raises(ValueError):
        portal.get_storage("")


def test_portal_config_get_storage_uses_explicit_connection_string() -> None:
    portal = _make_portal_config()

    storage = portal.get_storage("mssql+pyodbc://dummy")
    meta = storage.storage_meta
    assert meta.table_name == "TestTable"
    assert meta.schema == "dbo"
    assert meta.upsert_key == "timestamp"


def test_portal_config_get_repository_rejects_empty_connection_string() -> None:
    portal = _make_portal_config()

    with pytest.raises(ValueError):
        portal.get_repository("")


def test_portal_config_repr_hides_password() -> None:
    portal = _make_portal_config(password="supersecret")

    assert "supersecret" not in repr(portal)
    assert "***" in repr(portal)
