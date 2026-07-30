"""
scraper.interaction.actions.navigation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Navigation and DOM-waiting :class:`~scraper.interaction.base.AbstractFormAction`
implementations: clicking, direct navigation, key presses, and waiting for
selectors to appear.
"""

from __future__ import annotations

from typing import Any

from scraper.interaction.base import AbstractFormAction
from scraper.interaction.keys import Key, KeyCombo
from scraper.utils.logging import get_logger

logger = get_logger(__name__)


class ClickAction(AbstractFormAction):
    """Click an element identified by *selector*.

    Parameters:
        selector:          CSS selector of the element to click.
        wait_for_nav:      Wait for a page navigation after the click.
        wait_until:        Navigation wait condition (Playwright).
        timeout:           Timeout in ms.
    """

    def __init__(
        self,
        selector: str,
        wait_for_nav: bool = False,
        wait_until: str = "domcontentloaded",
        timeout: int = 30_000,
    ) -> None:
        self.selector     = selector
        self.wait_for_nav = wait_for_nav
        self.wait_until   = wait_until
        self.timeout      = timeout

    async def execute(self, page: Any) -> None:
        logger.debug("ClickAction: %s  wait_for_nav=%s", self.selector, self.wait_for_nav)
        if self.wait_for_nav:
            async with page.expect_navigation(
                wait_until=self.wait_until, timeout=self.timeout
            ):
                await page.click(self.selector)
        else:
            await page.click(self.selector)


class NavigateAction(AbstractFormAction):
    """Navigate directly to *url* within an interaction sequence.

    Parameters:
        url:        URL to navigate to (can be relative or absolute).
        wait_until: When to consider navigation finished (default ``"domcontentloaded"``).
        timeout:    Navigation timeout in ms.
    """

    def __init__(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30_000,
    ) -> None:
        self.url        = url
        self.wait_until = wait_until
        self.timeout    = timeout

    async def execute(self, page: Any) -> None:
        logger.debug("NavigateAction: -> %s", self.url)
        await page.goto(self.url, wait_until=self.wait_until, timeout=self.timeout)


class PressKeyAction(AbstractFormAction):
    """Press a key or key combination on a targeted element.

    Parameters:
        selector: CSS selector of the target element.
        key:      Key or key combination to press (e.g. ``Key.ENTER``, ``Key.CONTROL + "a"``).
    """

    def __init__(self, selector: str, key: Key | KeyCombo | str) -> None:
        self.selector = selector
        self.key = KeyCombo.from_input(key)
        if self.key is None:
            raise ValueError("PressKeyAction requires a valid key or KeyCombo")

    async def execute(self, page: Any) -> None:
        logger.debug("PressKeyAction: %s → %s", self.selector, self.key)
        await page.press(self.selector, str(self.key))


class WaitForAction(AbstractFormAction):
    """Pause until a CSS selector appears in the DOM.

    Parameters:
        selector: CSS selector to wait for.
        timeout:  Maximum wait time in ms.
        state:    Playwright visibility state: ``"visible"``, ``"attached"``,
                  ``"hidden"``, ``"detached"``.
    """

    def __init__(
        self,
        selector: str,
        timeout: int = 15_000,
        state: str = "visible",
    ) -> None:
        self.selector = selector
        self.timeout  = timeout
        self.state    = state

    async def execute(self, page: Any) -> None:
        logger.debug("WaitForAction: waiting for %s  state=%s", self.selector, self.state)
        await page.wait_for_selector(self.selector, timeout=self.timeout, state=self.state)
