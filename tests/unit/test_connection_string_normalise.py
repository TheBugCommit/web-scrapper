"""Unit tests for SQLServerStorage connection string normalization."""

from __future__ import annotations

import urllib.parse
from scraper.storage.sqlserver_storage import normalise_sqlserver_connection_string


def test_normalise_already_sqlalchemy_url() -> None:
    url = "mssql+pyodbc://user:pass@localhost/db?driver=ODBC+Driver+18+for+SQL+Server"
    norm = normalise_sqlserver_connection_string(url)
    assert norm.startswith("mssql+pyodbc:///?odbc_connect=")
    assert "SERVER%3Dlocalhost" in norm
    assert "DATABASE%3Ddb" in norm


def test_normalise_ssms_string() -> None:
    ssms = (
        "Data Source=DATABALFEGO\\DATAREPORTING;Persist Security Info=True;"
        "User ID=admin;Password=secret;Pooling=False;MultipleActiveResultSets=False;"
        "Encrypt=False;TrustServerCertificate=False;"
        'Application Name="SQL Server Management Studio";Command Timeout=0'
    )
    normalised = normalise_sqlserver_connection_string(ssms, default_db="Reporting_Test")
    assert normalised.startswith("mssql+pyodbc:///?odbc_connect=")

    # Decode the query parameter and inspect ODBC connection components
    query_param = normalised.split("?odbc_connect=", 1)[1]
    decoded = urllib.parse.unquote_plus(query_param)

    assert "SERVER=DATABALFEGO\\DATAREPORTING" in decoded
    assert "DATABASE=Reporting_Test" in decoded
    assert "UID=admin" in decoded
    assert "PWD=secret" in decoded
    assert "DRIVER={" in decoded
    assert "Encrypt=no" in decoded
    assert "TrustServerCertificate=yes" in decoded
