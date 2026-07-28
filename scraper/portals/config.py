"""
scraper.portals.config
~~~~~~~~~~~~~~~~~~~~~~
``PortalConfig`` — immutable descriptor for one web portal.

Contains everything needed to connect to a portal (URLs, field selectors,
browser options) and the credentials loaded from the secrets file
(never committed to version control).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.auth.form_auth import FormAuthHandler
    from scraper.storage.sqlserver_storage import SQLServerStorage


@dataclass(frozen=True)
class PortalConfig:
    """Descriptor for one web portal with merged public config + credentials.

    Attributes:
        key:              Unique identifier used as the YAML key and as the
                          env-var prefix (``{KEY_UPPER}_USERNAME`` / ``_PASSWORD``).
        name:             Human-readable display name.
        portal_url:       Main URL of the portal (also the scraper's start URL).
        login_url:        URL of the HTML login form.
        username:         Credential — loaded from ``.env.portals``, never YAML.
        password:         Credential — loaded from ``.env.portals``, never YAML.
        username_field:   CSS ``name`` attribute of the username input.
        password_field:   CSS ``name`` attribute of the password input.
        success_selector: CSS selector that appears only after a successful login.
        headless:         Whether Playwright should run in headless mode.
        extra:            Arbitrary portal-specific values (export URLs, IDs, etc.)
                          defined freely in ``portals.yml`` and accessed via
                          ``portal.extra["key"]``.
    """

    key: str
    name: str
    portal_url: str
    login_url: str
    username: str
    password: str
    username_field: str = "username"
    password_field: str = "password"
    success_selector: str = ""
    headless: bool = True
    db_table: str | None = None
    db_schema: str = "dbo"
    db_upsert_key: str | list[str] | None = None
    extra: dict = field(default_factory=dict, hash=False, compare=False)

    def form_auth(self) -> "FormAuthHandler":
        """Return a ready-to-use :class:`~scraper.auth.form_auth.FormAuthHandler`.

        Example::

            portal = registry.get("messer")
            session = ScraperBuilder()\\
                .with_auth(portal.form_auth())\\
                ...
        """
        from scraper.auth.form_auth import FormAuthHandler

        return FormAuthHandler(
            login_url=self.login_url,
            username=self.username,
            password=self.password,
            username_field=self.username_field,
            password_field=self.password_field,
            success_selector=self.success_selector,
        )

    def get_storage(self, connection_string: str | None = None) -> "SQLServerStorage":
        """Return a configured SQLServerStorage for this portal's table.

        Uses connection_string if passed, otherwise falls back to
        SCRAPER_DB_CONNECTION_STRING from the environment.
        """
        import os
        from scraper.storage.sqlserver_storage import SQLServerStorage

        conn_str = connection_string or os.getenv("SCRAPER_DB_CONNECTION_STRING")
        if not conn_str:
            raise ValueError(
                "No SQL Server connection string provided and SCRAPER_DB_CONNECTION_STRING "
                "is not set in the environment."
            )
        table = self.db_table or "scraped_data"
        schema = self.db_schema or "dbo"
        upsert_key = self.db_upsert_key

        return SQLServerStorage(
            connection_string=conn_str,
            table=table,
            upsert_key=upsert_key,
            schema_prefix=schema,
        )

    def __repr__(self) -> str:  # hide password from repr / logs
        return (
            f"PortalConfig(key={self.key!r}, name={self.name!r}, "
            f"portal_url={self.portal_url!r}, username={self.username!r}, "
            f"password='***')"
        )
