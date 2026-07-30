"""
scraper.interaction.interactors.form_interactor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`FormInteractor` — orchestrates an ordered list of
:class:`~scraper.interaction.base.AbstractFormAction`\\ s on a live page.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TYPE_CHECKING

from scraper.interaction.base import AbstractFormAction, AbstractPageInteractor, InteractionResult
from scraper.utils.cookies import dismiss_cookie_banners
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.core.context import ScraperContext

logger = get_logger(__name__)


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
        from scraper.interaction.actions import (
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
        url_pattern: str | None = None,
    ) -> None:
        self._actions             = actions
        self._screenshot_on_error = screenshot_on_error
        self._error_dir           = Path(error_dir)
        self._url_re              = re.compile(url_pattern) if url_pattern else None

    async def interact(
        self, page: Any, context: "ScraperContext"
    ) -> InteractionResult:
        """Execute all actions in order and return the final page state."""
        if self._url_re:
            current_url = getattr(page, "url", "")
            if current_url and not self._url_re.search(current_url):
                logger.debug(
                    "FormInteractor: skipping actions on %s (does not match url_pattern %r)",
                    current_url,
                    self._url_re.pattern,
                )
                content = await page.content()
                return InteractionResult(page_content=content, downloads=[])

        logger.debug("FormInteractor: running %d actions", len(self._actions))
        await dismiss_cookie_banners(page)

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

        content   = await page.content()
        downloads = [path for action in self._actions for path in action.downloads]

        logger.debug(
            "FormInteractor: done  downloads=%d", len(downloads)
        )
        return InteractionResult(
            page_content=content,
            downloads=downloads,
        )
