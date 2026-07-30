"""
scraper.interaction.base
~~~~~~~~~~~~~~~~~~~~~~~~
Abstract base classes for the page-interaction layer.

Interactions sit between page fetch and data extraction in the pipeline:

    fetch(url) → [interact: fill form, click, wait, download] → extract(HTML)

Architecture
------------
- ``AbstractFormAction`` — one atomic DOM action (select, check, click, download…)
- ``AbstractPageInteractor`` — orchestrates a sequence of actions on a live page
- ``InteractionResult`` — what the interactor returns (page HTML + any downloads)

Only ``PlaywrightBackend`` (or any backend that exposes a live page object) can
support interactors.  ``RequestsBackend`` silently skips them (it cannot
manipulate the DOM).  This keeps the system backward-compatible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.core.context import ScraperContext


@dataclass
class InteractionResult:
    """What a :class:`AbstractPageInteractor` produces after interacting.

    Attributes:
        page_content: Final HTML of the page after all actions have run.
                      Used by extractors downstream.
        downloads:    List of local file paths produced by any
                      :class:`~scraper.interaction.actions.download.DownloadSubmitAction`.
        metadata:     Arbitrary key-value data attached by actions.
    """

    page_content: str = ""
    downloads: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AbstractFormAction(ABC):
    """One atomic DOM interaction applied to a live Playwright page.

    Implement this to create new interaction types (e.g. drag-and-drop,
    file-upload, CAPTCHA solver hook, etc.).

    The ``downloads`` property allows actions that trigger file downloads
    to surface the resulting local path to the orchestrating interactor.
    """

    @abstractmethod
    async def execute(self, page: Any) -> None:
        """Apply this action to *page* (a Playwright ``Page`` object).

        Args:
            page: A live ``playwright.async_api.Page`` instance.
        """

    @property
    def downloads(self) -> list[str]:
        """Return local paths of any files downloaded by this action."""
        return []


class AbstractPageInteractor(ABC):
    """Orchestrates a sequence of :class:`AbstractFormAction`\\ s on a page.

    Register via :meth:`~scraper.core.builder.ScraperBuilder.with_interaction`.

    Example::

        from scraper.interaction import FormInteractor
        from scraper.interaction.actions import SelectAction, CheckboxAction

        interactor = FormInteractor(actions=[
            SelectAction("select[name='month']", "7"),
            CheckboxAction("input#agree", checked=True),
        ])
    """

    @abstractmethod
    async def interact(
        self, page: Any, context: "ScraperContext"
    ) -> InteractionResult:
        """Run all DOM interactions and return the result.

        Args:
            page:    A live Playwright ``Page`` already navigated to the target URL.
            context: Shared scraping configuration.

        Returns:
            :class:`InteractionResult` with the final page HTML and any downloads.
        """
