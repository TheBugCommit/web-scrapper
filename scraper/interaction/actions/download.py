"""
scraper.interaction.actions.download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`~scraper.interaction.base.AbstractFormAction` implementation that
triggers and captures a file download.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.interaction.base import AbstractFormAction
from scraper.utils.logging import get_logger

logger = get_logger(__name__)


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
