"""
scraper.core.builder
~~~~~~~~~~~~~~~~~~~~
Fluent builder that assembles a :class:`ScraperSession`.

Usage example::

    from scraper import ScraperBuilder
    from scraper.auth import FormAuthHandler
    from scraper.backends import PlaywrightBackend
    from scraper.extractors import CSSExtractor
    from scraper.navigation import PaginationNavigator
    from scraper.storage import SQLServerStorage

    session = (
        ScraperBuilder()
        .with_url("https://portal.example.com")
        .with_auth(FormAuthHandler(
            login_url="https://portal.example.com/login",
            username_field="username",
            password_field="password",
            username="myuser",
            password="mypass",
        ))
        .with_backend(PlaywrightBackend())
        .with_navigator(PaginationNavigator(next_selector="a.next"))
        .with_extractor(CSSExtractor(rules={"title": "h1", "price": ".price"}))
        .with_storage(SQLServerStorage.from_env())
        .build()
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scraper.core.context import ScraperContext
from scraper.core.session import ScraperSession

if TYPE_CHECKING:
    from scraper.auth.base import AbstractAuthHandler
    from scraper.backends.base import AbstractBackend
    from scraper.extractors.base import AbstractExtractor
    from scraper.interaction.base import AbstractPageInteractor
    from scraper.navigation.base import AbstractNavigator
    from scraper.storage.base import AbstractStorage


class ScraperBuilder:
    """Fluent builder for :class:`~scraper.core.session.ScraperSession`.

    All ``with_*`` methods return *self* to allow method chaining.
    Call :meth:`build` to produce the finished session.
    """

    def __init__(self) -> None:
        self._context: ScraperContext | None = None
        self._backend: "AbstractBackend | None" = None
        self._auth: "AbstractAuthHandler | None" = None
        self._interactors: list["AbstractPageInteractor"] = []
        self._navigators: list["AbstractNavigator"] = []
        self._extractors: list["AbstractExtractor"] = []
        self._storage: "AbstractStorage | None" = None
        self._start_urls: list[str] = []

    # ── Context / URL ──────────────────────────────────────────────────────

    def with_url(self, url: str) -> "ScraperBuilder":
        """Set the base / seed URL for the session."""
        self._start_urls = [url]
        return self

    def with_urls(self, urls: list[str]) -> "ScraperBuilder":
        """Set multiple seed URLs (all will be scraped concurrently)."""
        self._start_urls = list(urls)
        return self

    def with_context(self, context: ScraperContext) -> "ScraperBuilder":
        """Provide a fully-configured :class:`ScraperContext` directly."""
        self._context = context
        return self

    # ── Backend ────────────────────────────────────────────────────────────

    def with_backend(self, backend: "AbstractBackend") -> "ScraperBuilder":
        """Choose the HTTP/browser backend (e.g. RequestsBackend or PlaywrightBackend)."""
        self._backend = backend
        return self

    # ── Auth ───────────────────────────────────────────────────────────────

    def with_auth(self, handler: "AbstractAuthHandler") -> "ScraperBuilder":
        """Attach an authentication handler executed once before scraping."""
        self._auth = handler
        return self

    # ── Interaction ────────────────────────────────────────────────────────

    def with_interaction(self, interactor: "AbstractPageInteractor") -> "ScraperBuilder":
        """Append a page interactor run between fetch and extraction.

        Interactors allow complex DOM interactions (filling forms, clicking
        buttons, handling file downloads) to be described declaratively and
        executed by the engine without exposing the browser API.

        Multiple interactors are applied in registration order.  Only
        :class:`~scraper.backends.playwright_backend.PlaywrightBackend`
        supports interactors; other backends silently skip them.
        """
        self._interactors.append(interactor)
        return self

    def with_interactions(self, interactors: list["AbstractPageInteractor"]) -> "ScraperBuilder":
        """Register multiple interactors at once."""
        self._interactors.extend(interactors)
        return self

    # ── Navigation ─────────────────────────────────────────────────────────

    def with_navigator(self, navigator: "AbstractNavigator") -> "ScraperBuilder":
        """Append a navigator (link follower, paginator, etc.)."""
        self._navigators.append(navigator)
        return self

    # ── Extractors ─────────────────────────────────────────────────────────

    def with_extractor(self, extractor: "AbstractExtractor") -> "ScraperBuilder":
        """Append a data extractor applied to every fetched page."""
        self._extractors.append(extractor)
        return self

    # ── Storage ────────────────────────────────────────────────────────────

    def with_storage(self, storage: "AbstractStorage") -> "ScraperBuilder":
        """Set the storage sink where extracted rows are persisted."""
        self._storage = storage
        return self

    # ── Build ──────────────────────────────────────────────────────────────

    def build(self) -> ScraperSession:
        """Validate configuration and return a :class:`ScraperSession`.

        Raises:
            ValueError: If a mandatory component (backend) is missing.
        """
        if self._backend is None:
            raise ValueError(
                "A backend is required. Call .with_backend() before .build()."
            )

        # Warn if interactors are registered with a non-interactive backend
        if self._interactors and not hasattr(self._backend, "get_interactive"):
            import logging
            logging.getLogger(__name__).warning(
                "ScraperBuilder: interactors registered but backend %s does not "
                "support get_interactive() — interactors will be skipped. "
                "Use PlaywrightBackend for interactive sessions.",
                type(self._backend).__name__,
            )

        # Build a default context if the caller did not supply one explicitly.
        if self._context is None:
            base = self._start_urls[0] if self._start_urls else ""
            self._context = ScraperContext(base_url=base)

        return ScraperSession(
            context=self._context,
            backend=self._backend,
            auth=self._auth,
            interactors=list(self._interactors),
            navigators=list(self._navigators),
            extractors=list(self._extractors),
            storage=self._storage,
            start_urls=list(self._start_urls),
        )
