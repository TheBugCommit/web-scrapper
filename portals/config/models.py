"""
portals.config.models
~~~~~~~~~~~~~~~~~~~~~
``PortalConfig`` — immutable descriptor for one web portal.

Contains everything needed to connect to a portal (URLs, field selectors,
browser options) and the credentials loaded from the secrets file
(never committed to version control).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scraper.auth.form_auth import FormAuthHandler
    from scraper.core.builder import ScraperBuilder
    from scraper.storage.repository import SQLServerRepository
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
        username:         Credential loaded from secrets file / environment.
        password:         Credential loaded from secrets file / environment.
        username_field:   HTML ``name`` attribute of username input.
        password_field:   HTML ``name`` attribute of password input.
        submit_selector:  CSS selector of the submit button.
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
    submit_selector: str = "button[type='submit'], input[type='submit'], [type=submit], button.button--default, button"
    success_selector: str = ""
    headless: bool = True
    db_table: str | None = None
    db_schema: str = "dbo"
    db_upsert_key: str | list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def form_auth(self) -> "FormAuthHandler":
        """Return a ready-to-use :class:`~scraper.auth.form_auth.FormAuthHandler`."""
        from scraper.auth.form_auth import FormAuthHandler

        return FormAuthHandler(
            login_url=self.login_url,
            username=self.username,
            password=self.password,
            username_field=self.username_field,
            password_field=self.password_field,
            submit_selector=self.submit_selector,
            success_selector=self.success_selector,
        )

    def get_storage(self, connection_string: str | None = None) -> SQLServerStorage:
        """Return a configured SQLServerStorage for this portal's table."""
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

    def get_repository(self, connection_string: str | None = None) -> SQLServerRepository:
        """Return a configured SQLServerRepository for this portal's schema."""
        import os
        from scraper.storage.repository import SQLServerRepository

        conn_str = connection_string or os.getenv("SCRAPER_DB_CONNECTION_STRING")
        if not conn_str:
            raise ValueError(
                "No SQL Server connection string provided and SCRAPER_DB_CONNECTION_STRING "
                "is not set in the environment."
            )
        schema = self.db_schema or "dbo"
        return SQLServerRepository(connection_string=conn_str, default_schema=schema)

    def get_builder(self, url: str | None = None) -> "ScraperBuilder":
        """Return a pre-configured ScraperBuilder with generic environment settings."""
        import os
        from scraper.backends import PlaywrightBackend
        from scraper.core.builder import ScraperBuilder

        max_concurrent = int(os.getenv("SCRAPER_MAX_CONCURRENT", "5"))
        max_retries = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
        rate_limit_delay = float(os.getenv("SCRAPER_RATE_LIMIT_DELAY", "1.0"))
        timeout_ms = int(os.getenv("SCRAPER_TIMEOUT_MS", "90000"))
        debug_mode = os.getenv("SCRAPER_DEBUG", "false").lower() in ("1", "true", "yes")

        headless_env = os.getenv("SCRAPER_HEADLESS")
        headless = (
            headless_env.lower() in ("1", "true", "yes")
            if headless_env is not None
            else self.headless
        )

        target_url = url or self.portal_url

        return (
            ScraperBuilder()
            .with_url(target_url)
            .with_backend(PlaywrightBackend(headless=headless, timeout=timeout_ms))
            .with_auth(self.form_auth())
            .with_headless(headless)
            .with_max_concurrent(max_concurrent)
            .with_max_retries(max_retries)
            .with_rate_limit_delay(rate_limit_delay)
            .with_debug_mode(debug_mode)
        )

    def __repr__(self) -> str:  # hide password from repr / logs
        return (
            f"PortalConfig(key={self.key!r}, name={self.name!r}, "
            f"portal_url={self.portal_url!r}, username={self.username!r}, "
            f"password='***')"
        )
