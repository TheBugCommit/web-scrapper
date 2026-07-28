"""
scraper.interaction.form_actions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Concrete :class:`~scraper.interaction.base.AbstractFormAction` implementations
for common HTML form interactions.

Available actions
-----------------
=========================  ==========================================================
Class                      What it does
=========================  ==========================================================
:class:`SelectAction`      Set a ``<select>`` value; optional auto-submit wait
:class:`CheckboxAction`    Check / uncheck a single checkbox
:class:`UncheckAllAction`  Uncheck every checkbox matching a selector
:class:`ClickAction`       Click any element; optional navigation wait
:class:`FillAction`        Type text into an ``<input>`` or ``<textarea>``
:class:`WaitForAction`     Wait until a CSS selector appears in the DOM
:class:`DownloadSubmitAction` Click a submit button and capture the downloaded file
=========================  ==========================================================

All actions operate on a live Playwright ``Page`` object supplied by
:class:`~scraper.interaction.form_actions.FormInteractor`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from scraper.interaction.base import AbstractFormAction, AbstractPageInteractor, InteractionResult
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.core.context import ScraperContext

logger = get_logger(__name__)


# ── SelectAction ───────────────────────────────────────────────────────────────

class SelectAction(AbstractFormAction):
    """Set the value of a ``<select>`` element.

    Parameters:
        selector:    CSS selector of the ``<select>`` element.
        value:       Option value to select (the ``value`` attribute of ``<option>``).
        auto_submit: If *True*, the selection triggers a form ``onchange`` → submit.
                     The action will wait for the resulting page navigation to finish
                     before returning control to the next action.
        timeout:     Navigation wait timeout in ms (only used when ``auto_submit=True``).
    """

    def __init__(
        self,
        selector: str,
        value: str,
        auto_submit: bool = False,
        timeout: int = 30_000,
    ) -> None:
        self.selector    = selector
        self.value       = value
        self.auto_submit = auto_submit
        self.timeout     = timeout

    async def execute(self, page: Any) -> None:
        logger.debug("SelectAction: %s → %s", self.selector, self.value)
        if self.auto_submit:
            async with page.expect_navigation(
                wait_until="domcontentloaded", timeout=self.timeout
            ):
                await page.select_option(self.selector, self.value)
            logger.debug("SelectAction: navigation after auto-submit complete")
        else:
            await page.select_option(self.selector, self.value)


# ── CheckboxAction ─────────────────────────────────────────────────────────────

class CheckboxAction(AbstractFormAction):
    """Check or uncheck a single checkbox.

    Parameters:
        selector: CSS selector of the ``<input type="checkbox">`` element.
        checked:  *True* to check, *False* to uncheck.
    """

    def __init__(self, selector: str, checked: bool = True) -> None:
        self.selector = selector
        self.checked  = checked

    async def execute(self, page: Any) -> None:
        logger.debug("CheckboxAction: %s → %s", self.selector, self.checked)
        if self.checked:
            await page.check(self.selector)
        else:
            await page.uncheck(self.selector)


# ── UncheckAllAction ───────────────────────────────────────────────────────────

class UncheckAllAction(AbstractFormAction):
    """Uncheck **all** checkboxes matching *selector*.

    Useful as a reset before selectively re-checking specific checkboxes.

    Parameters:
        selector: CSS selector that matches one or more checkboxes.
    """

    def __init__(self, selector: str) -> None:
        self.selector = selector

    async def execute(self, page: Any) -> None:
        checkboxes = await page.query_selector_all(self.selector)
        logger.debug("UncheckAllAction: unchecking %d checkboxes", len(checkboxes))
        for cb in checkboxes:
            await cb.uncheck()


# ── ClickAction ────────────────────────────────────────────────────────────────

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


# ── FillAction ─────────────────────────────────────────────────────────────────

class FillAction(AbstractFormAction):
    """Type *text* into a text input or textarea.

    Parameters:
        selector: CSS selector of the input element.
        text:     Text to type.
    """

    def __init__(self, selector: str, text: str) -> None:
        self.selector = selector
        self.text     = text

    async def execute(self, page: Any) -> None:
        logger.debug("FillAction: %s ← %r", self.selector, self.text)
        await page.fill(self.selector, self.text)


# ── WaitForAction ──────────────────────────────────────────────────────────────

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


# ── DownloadSubmitAction ───────────────────────────────────────────────────────

class DownloadSubmitAction(AbstractFormAction):
    """Click a submit element and capture the file download that it triggers.

    The downloaded file is saved to *download_dir* using the server-suggested
    filename.  The local path is accessible via :attr:`downloads` after
    the action has executed.

    Parameters:
        selector:     CSS selector of the submit button / link.
        download_dir: Local directory where the file will be saved.
        timeout:      Download wait timeout in ms.
    """

    def __init__(
        self,
        selector: str,
        download_dir: str | Path = "./downloads",
        timeout: int = 60_000,
    ) -> None:
        self.selector     = selector
        self.download_dir = Path(download_dir)
        self.timeout      = timeout
        self._path: str | None = None

    async def execute(self, page: Any) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("DownloadSubmitAction: clicking %s, awaiting download…", self.selector)

        async with page.expect_download(timeout=self.timeout) as dl_info:
            await page.click(self.selector)

        download    = await dl_info.value
        filename    = download.suggested_filename or "download"
        target      = self.download_dir / filename
        await download.save_as(str(target))
        self._path  = str(target)
        logger.info("DownloadSubmitAction: saved → %s", target)

    @property
    def downloads(self) -> list[str]:
        return [self._path] if self._path else []


# ── FormInteractor ─────────────────────────────────────────────────────────────

class FormInteractor(AbstractPageInteractor):
    """Orchestrates an ordered list of :class:`AbstractFormAction`\\ s on a page.

    The interactor applies each action sequentially, collects all downloads
    produced, and returns the final rendered HTML.

    Parameters:
        actions:         Ordered list of actions to execute.
        screenshot_on_error: Save a screenshot to *error_dir* if any action fails.
        error_dir:       Directory for error screenshots.

    Example::

        from scraper.interaction import FormInteractor
        from scraper.interaction.form_actions import (
            SelectAction, UncheckAllAction, CheckboxAction, DownloadSubmitAction,
        )

        interactor = FormInteractor(actions=[
            SelectAction("select[name='modul_id']", "244425", auto_submit=True),
            SelectAction("select[name='dateTrunc']", "hour"),
            UncheckAllAction("input[type='checkbox'][name='channelList']"),
            CheckboxAction("input[name='channelList'][value='EAN000']", checked=True),
            CheckboxAction("input[name='channelList'][value='EAN001']", checked=True),
            DownloadSubmitAction("input[type='submit'][name='createLink']", "./downloads"),
        ])
    """

    def __init__(
        self,
        actions: list[AbstractFormAction],
        screenshot_on_error: bool = True,
        error_dir: str | Path = "./downloads",
    ) -> None:
        self._actions            = actions
        self._screenshot_on_error = screenshot_on_error
        self._error_dir          = Path(error_dir)

    async def interact(
        self, page: Any, context: "ScraperContext"
    ) -> InteractionResult:
        """Execute all actions in order and return the final page state."""
        logger.debug("FormInteractor: running %d actions", len(self._actions))

        try:
            for i, action in enumerate(self._actions):
                logger.debug(
                    "  [%d/%d] %s", i + 1, len(self._actions), type(action).__name__
                )
                await action.execute(page)
        except Exception as exc:
            logger.error("FormInteractor: action failed — %s", exc)
            if self._screenshot_on_error:
                from datetime import date
                self._error_dir.mkdir(parents=True, exist_ok=True)
                shot = self._error_dir / f"error_{date.today().isoformat()}.png"
                await page.screenshot(path=str(shot))
                logger.error("  Screenshot saved → %s", shot)
            raise

        # Collect final HTML and any downloads
        content   = await page.content()
        downloads = [path for action in self._actions for path in action.downloads]

        logger.debug(
            "FormInteractor: done  downloads=%d", len(downloads)
        )
        return InteractionResult(
            page_content=content,
            downloads=downloads,
        )
