"""
scraper.auth.form_auth
~~~~~~~~~~~~~~~~~~~~~~
HTML form-based authentication handler.

Supports both static HTML forms (via :class:`~scraper.backends.requests_backend.RequestsBackend`)
and JavaScript-rendered login pages (via :class:`~scraper.backends.playwright_backend.PlaywrightBackend`).

For Playwright backends the handler will:
1. Navigate to the login URL.
2. Fill in the username / password fields identified by their CSS selectors.
3. Click the submit button (or press Enter).
4. Wait for navigation to complete.
5. Optionally verify that a post-login element is present (to detect failures).

For HTTP-only backends the handler will:
1. GET the login page to harvest the form action URL and CSRF token.
2. POST the credentials along with any hidden fields.
3. Follow redirects automatically.
4. Verify the session cookie is present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from scraper.auth.base import AbstractAuthHandler, AuthenticationError
from scraper.backends.base import AbstractBackend
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.core.context import ScraperContext

logger = get_logger(__name__)


class FormAuthHandler(AbstractAuthHandler):
    """Authenticate against an HTML login form.

    Parameters:
        login_url:          URL of the login page / POST action endpoint.
        username:           Credential — username or email.
        password:           Credential — password.
        username_field:     ``name`` attribute of the username input.
        password_field:     ``name`` attribute of the password input.
        submit_selector:    CSS selector of the submit button (Playwright only).
        success_selector:   CSS selector that must be present after login to
                            confirm success (optional but recommended).
        extra_fields:       Additional form fields (e.g. tenant ID, CSRF token
                            override, remember-me checkbox).
        post_login_url:     URL to navigate to after login (optional).
    """

    def __init__(
        self,
        login_url: str,
        username: str,
        password: str,
        username_field: str = "username",
        password_field: str = "password",
        submit_selector: str = "[type=submit]",
        success_selector: str | None = None,
        extra_fields: dict[str, str] | None = None,
        post_login_url: str | None = None,
    ) -> None:
        self._login_url = login_url
        self._username = username
        self._password = password
        self._username_field = username_field
        self._password_field = password_field
        self._submit_selector = submit_selector
        self._success_selector = success_selector
        self._extra_fields = extra_fields or {}
        self._post_login_url = post_login_url

    # ── AbstractAuthHandler ───────────────────────────────────────────────

    async def authenticate(
        self, backend: AbstractBackend, context: "ScraperContext"
    ) -> None:
        """Detect backend type and delegate to the appropriate login flow."""
        # Late import to avoid circular dependency
        from scraper.backends.playwright_backend import PlaywrightBackend

        if isinstance(backend, PlaywrightBackend):
            await self._playwright_login(backend, context)
        else:
            await self._http_login(backend, context)

    # ── Playwright login ──────────────────────────────────────────────────

    async def _playwright_login(
        self, backend: "Any", context: "ScraperContext"
    ) -> None:
        logger.info("FormAuth (Playwright): navigating to %s", self._login_url)
        page = await backend.new_page()
        try:
            await page.goto(
                self._login_url, timeout=30_000, wait_until="domcontentloaded"
            )

            # Fill extra hidden fields first
            for name, value in self._extra_fields.items():
                try:
                    await page.fill(f"[name={name}]", value)
                except Exception:  # noqa: BLE001
                    pass  # field may not exist on this form

            await page.fill(f"[name={self._username_field}]", self._username)
            await page.fill(f"[name={self._password_field}]", self._password)

            logger.debug("FormAuth: submitting form")
            async with page.expect_navigation(timeout=30_000):
                await page.click(self._submit_selector)

            # Navigate to post-login URL if specified
            if self._post_login_url:
                await page.goto(self._post_login_url, wait_until="networkidle")

            # Verify login success
            if self._success_selector:
                element = await page.query_selector(self._success_selector)
                if element is None:
                    raise AuthenticationError(
                        f"Login failed: success element '{self._success_selector}' "
                        f"not found after submitting form at {self._login_url}"
                    )

            logger.info("FormAuth (Playwright): ✅ authenticated successfully")
        finally:
            await page.close()

    # ── HTTP-only login ───────────────────────────────────────────────────

    async def _http_login(
        self, backend: AbstractBackend, context: "ScraperContext"
    ) -> None:
        logger.info("FormAuth (HTTP): fetching login page %s", self._login_url)

        # Step 1 — GET the login page to harvest hidden fields + form action
        login_page = await backend.get(self._login_url)
        soup = BeautifulSoup(login_page.content, "lxml")

        form = soup.find("form")
        if not form:
            raise AuthenticationError(
                f"No <form> element found on login page: {self._login_url}"
            )

        # Determine the POST action URL
        action: str = form.get("action", self._login_url)  # type: ignore[assignment]
        if not action.startswith("http"):
            from urllib.parse import urljoin
            action = urljoin(self._login_url, action)

        # Harvest all hidden fields (CSRF tokens, honeypots, etc.)
        post_data: dict[str, str] = {}
        for hidden in form.find_all("input", type="hidden"):
            name = hidden.get("name", "")
            value = hidden.get("value", "")
            if name:
                post_data[name] = value

        # Add credentials + any caller-supplied overrides
        post_data[self._username_field] = self._username
        post_data[self._password_field] = self._password
        post_data.update(self._extra_fields)

        # Step 2 — POST credentials
        logger.debug("FormAuth: POSTing to %s  fields=%s", action, list(post_data.keys()))
        response = await backend.post(action, data=post_data)

        # Step 3 — Verify session
        if self._success_selector:
            resp_soup = BeautifulSoup(response.content, "lxml")
            if not resp_soup.select(self._success_selector):
                raise AuthenticationError(
                    f"Login failed: success selector '{self._success_selector}' "
                    f"not found in response from {action}"
                )

        if not response.cookies and not backend.get_cookies():
            logger.warning(
                "FormAuth: no session cookies detected after login — "
                "the portal may require a success_selector check."
            )

        logger.info("FormAuth (HTTP): ✅ authenticated successfully")

        # Navigate to post-login URL if specified
        if self._post_login_url:
            await backend.get(self._post_login_url)
