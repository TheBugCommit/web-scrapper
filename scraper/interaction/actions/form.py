"""
scraper.interaction.actions.form
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Form-field :class:`~scraper.interaction.base.AbstractFormAction` implementations:
selecting options, and checking/unchecking checkboxes.
"""

from __future__ import annotations

from typing import Any

from scraper.interaction.base import AbstractFormAction
from scraper.interaction.keys import Key, KeyCombo
from scraper.utils.logging import get_logger

logger = get_logger(__name__)


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


class FillAction(AbstractFormAction):
    """Type *text* into a text input or textarea.

    Parameters:
        selector:  CSS selector of the input element.
        text:      Text to type.
        press_key: Optional key or key combination to press after filling
                   (e.g. ``Key.ENTER``, ``Key.CONTROL + "a"``, ``KeyCombo.ctrl("Enter")``,
                   or string ``"Enter"``).
    """

    def __init__(
        self,
        selector: str,
        text: str,
        press_key: Key | KeyCombo | str | None = None,
    ) -> None:
        self.selector  = selector
        self.text      = text
        self.press_key: KeyCombo | None = KeyCombo.from_input(press_key)

    async def execute(self, page: Any) -> None:
        logger.debug("FillAction: %s ← %r (press_key=%s)", self.selector, self.text, self.press_key)
        await page.fill(self.selector, self.text)
        if self.press_key:
            await page.press(self.selector, str(self.press_key))
