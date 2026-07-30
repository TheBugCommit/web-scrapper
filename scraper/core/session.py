"""
scraper.core.session
~~~~~~~~~~~~~~~~~~~~
A *ScraperSession* is an immutable description of a single scraping job:
what to scrape, how to authenticate, how to navigate, what to extract,
and where to store results.

Sessions are created exclusively via ``ScraperBuilder`` to ensure all
required components are provided before execution begins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.auth.base import AbstractAuthHandler
    from scraper.backends.base import AbstractBackend
    from scraper.extractors.base import AbstractExtractor
    from scraper.interaction.base import AbstractPageInteractor
    from scraper.navigation.base import AbstractNavigator
    from scraper.storage.base import AbstractStorage
    from scraper.core.context import ScraperContext


@dataclass
class ScraperSession:
    """Fully-configured scraping job ready to be handed to the engine.

    Attributes:
        context:     Shared configuration (URLs, limits, env vars).
        backend:     HTTP/browser backend used to fetch pages.
        auth:        Optional authentication handler (e.g. HTML form login).
        interactors: Ordered list of page interactors applied after fetching.
                     Used for complex form interactions, downloads, etc.
                     Only executed when the backend supports ``get_interactive()``.
        navigators:  Ordered list of navigators that discover next pages.
        extractors:  Ordered list of extractors applied to each page.
        storage:     Optional sink where extracted rows are persisted.
        start_urls:  One or more seed URLs; falls back to ``context.base_url``.
    """

    context: "ScraperContext"
    backend: "AbstractBackend"
    auth: "AbstractAuthHandler | None" = None
    interactors: list["AbstractPageInteractor"] = field(default_factory=list)
    navigators: list["AbstractNavigator"] = field(default_factory=list)
    extractors: list["AbstractExtractor"] = field(default_factory=list)
    storage: "AbstractStorage | None" = None
    start_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.start_urls and self.context.base_url:
            self.start_urls = [self.context.base_url]
