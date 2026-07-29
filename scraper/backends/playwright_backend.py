"""
scraper.backends.playwright_backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
JS-capable backend powered by Microsoft Playwright (async API).

This backend launches a real Chromium / Firefox / WebKit browser instance
and renders pages with full JavaScript execution.  It shares cookies
across requests through the same :class:`playwright.async_api.BrowserContext`.

Usage::

    async with PlaywrightBackend(browser="chromium", headless=True) as backend:
        response = await backend.get("https://spa-app.example.com")

Playwright must be installed separately::

    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

from typing import Any, Literal

from scraper.backends.base import AbstractBackend, PageResponse
from scraper.utils.cookies import dismiss_cookie_banners
from scraper.utils.logging import get_logger

logger = get_logger(__name__)

BrowserType = Literal["chromium", "firefox", "webkit"]


class PlaywrightBackend(AbstractBackend):
    """Browser backend that renders JavaScript pages via Playwright.

    Parameters:
        browser:     Browser engine to use (``"chromium"``, ``"firefox"``, ``"webkit"``).
        headless:    Run in headless mode (no visible window).
        timeout:     Navigation timeout in milliseconds.
        slow_mo:     Slow down Playwright operations by this many ms (useful for debugging).
        extra_args:  Additional browser launch arguments.
        wait_until:  When to consider navigation finished.
                     Options: ``"load"``, ``"domcontentloaded"``, ``"networkidle"``.
    """

    def __init__(
        self,
        browser: BrowserType = "chromium",
        headless: bool = True,
        timeout: int = 30_000,
        slow_mo: int = 0,
        extra_args: list[str] | None = None,
        wait_until: str = "networkidle",
    ) -> None:
        self._browser_type = browser
        self._headless = headless
        self._timeout = timeout
        self._slow_mo = slow_mo
        self._extra_args = extra_args or []
        self._wait_until = wait_until

        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def open(self) -> None:
        from playwright.async_api import async_playwright  # lazy import

        logger.debug(
            "PlaywrightBackend: launching %s  headless=%s",
            self._browser_type,
            self._headless,
        )
        self._playwright = await async_playwright().start()
        launcher = getattr(self._playwright, self._browser_type)
        self._browser = await launcher.launch(
            headless=self._headless,
            slow_mo=self._slow_mo,
            args=self._extra_args,
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )
        logger.debug("PlaywrightBackend: browser context ready")

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.debug("PlaywrightBackend: browser closed")

    # ── Internal helpers ──────────────────────────────────────────────────

    def _context_or_raise(self) -> Any:
        if self._context is None:
            raise RuntimeError(
                "Backend is not open. Use it as an async context manager."
            )
        return self._context

    async def _page_to_response(self, page: Any, url: str) -> PageResponse:
        """Serialise a Playwright Page into a :class:`PageResponse`."""
        content = await page.content()
        response_obj = page.url  # final URL after redirects
        # Retrieve cookies from the context
        cookies_raw = await self._context.cookies()
        cookies = {c["name"]: c["value"] for c in cookies_raw}
        return PageResponse(
            url=response_obj,
            status_code=200,  # Playwright does not expose status on page directly
            content=content,
            cookies=cookies,
        )

    # ── HTTP primitives ───────────────────────────────────────────────────

    async def get(self, url: str, **kwargs: Any) -> PageResponse:
        """Navigate to *url* and return fully-rendered HTML."""
        ctx = self._context_or_raise()
        page = await ctx.new_page()
        try:
            logger.debug("Playwright GET %s", url)
            await page.goto(url, timeout=self._timeout, wait_until=self._wait_until)
            await dismiss_cookie_banners(page)
            return await self._page_to_response(page, url)
        finally:
            await page.close()

    async def get_interactive(
        self,
        url: str,
        interactors: list[Any],
        context: Any = None,
    ) -> PageResponse:
        """Navigate to *url*, apply *interactors* on the live page, return response.

        This is the entry point used by :class:`~scraper.core.engine.ScraperEngine`
        when the session has registered interactors.  The live ``Page`` object is
        passed directly to each interactor so they can fill forms, click buttons,
        handle downloads, etc., without any Playwright code leaking into user scripts.

        Args:
            url:         Target URL to navigate to.
            interactors: Ordered list of :class:`~scraper.interaction.base.AbstractPageInteractor`.
            context:     Shared :class:`~scraper.core.context.ScraperContext` (optional).

        Returns:
            :class:`~scraper.backends.base.PageResponse` with ``metadata["downloads"]``
            populated with the local paths of any downloaded files.
        """
        from scraper.core.context import ScraperContext  # avoid circular import

        ctx_obj = context if isinstance(context, ScraperContext) else ScraperContext()
        browser_ctx = self._context_or_raise()
        page = await browser_ctx.new_page()
        try:
            logger.debug("Playwright GET (interactive) %s", url)
            await page.goto(url, timeout=self._timeout, wait_until=self._wait_until)
            await dismiss_cookie_banners(page)

            all_downloads: list[str] = []
            final_content: str = await page.content()

            for interactor in interactors:
                result = await interactor.interact(page, ctx_obj)
                if result.page_content:
                    final_content = result.page_content
                all_downloads.extend(result.downloads)

            cookies_raw = await browser_ctx.cookies()
            cookies = {c["name"]: c["value"] for c in cookies_raw}

            return PageResponse(
                url=page.url,
                status_code=200,
                content=final_content,
                cookies=cookies,
                metadata={"downloads": all_downloads},
            )
        finally:
            await page.close()

    async def post(
        self, url: str, data: dict[str, str], **kwargs: Any
    ) -> PageResponse:
        """Submit a form via JavaScript fetch / direct POST navigation.

        For most form logins use :class:`~scraper.auth.form_auth.FormAuthHandler`
        which drives the actual DOM form.  This method is a convenience wrapper.
        """
        ctx = self._context_or_raise()
        page = await ctx.new_page()
        try:
            logger.debug("Playwright POST %s", url)
            # Use the Playwright request API for raw POST
            response = await page.request.post(url, form=data)
            content = await response.text()
            cookies_raw = await self._context.cookies()
            cookies = {c["name"]: c["value"] for c in cookies_raw}
            return PageResponse(
                url=url,
                status_code=response.status,
                content=content,
                headers=dict(response.headers),
                cookies=cookies,
            )
        finally:
            await page.close()

    # ── Cookie helpers ────────────────────────────────────────────────────

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """Inject cookies into the shared browser context."""
        if self._context is None:
            raise RuntimeError("Backend is not open.")
        import asyncio

        cookie_list = [{"name": k, "value": v, "url": "about:blank"} for k, v in cookies.items()]
        asyncio.get_event_loop().run_until_complete(self._context.add_cookies(cookie_list))

    def get_cookies(self) -> dict[str, str]:
        if self._context is None:
            return {}
        import asyncio

        cookies_raw = asyncio.get_event_loop().run_until_complete(self._context.cookies())
        return {c["name"]: c["value"] for c in cookies_raw}

    # ── Playwright-specific helpers ───────────────────────────────────────

    async def new_page(self) -> Any:
        """Return a raw Playwright :class:`~playwright.async_api.Page`.

        Use this for advanced interactions (clicking, filling forms, etc.)
        in custom auth handlers or navigators.
        """
        return await self._context_or_raise().new_page()
