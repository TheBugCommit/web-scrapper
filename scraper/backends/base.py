"""
scraper.backends.base
~~~~~~~~~~~~~~~~~~~~~
Abstract base class for all HTTP / browser backends.

A backend is responsible for:
- Maintaining a persistent session (cookies, headers, auth state)
- Fetching pages (GET / POST)
- Returning a :class:`PageResponse` with the raw HTML content

Backends are async context managers so they can manage connection pools,
browser instances, or any other resource that needs explicit teardown.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PageResponse:
    """Normalised result returned by any backend after fetching a URL.

    Attributes:
        url:         Final URL after any redirects.
        status_code: HTTP status code.
        content:     Full page HTML (or JSON text for API backends).
        headers:     Response headers.
        cookies:     Cookies set by the server.
    """

    url: str
    status_code: int
    content: str
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    """Extra data produced by the backend or interaction layer.

    Keys of interest:
    - ``"downloads"``: list[str] — local paths of files downloaded during interaction.
    """

    @property
    def ok(self) -> bool:
        """Return *True* for 2xx status codes."""
        return 200 <= self.status_code < 300


class AbstractBackend(ABC):
    """Strategy interface for HTTP/browser backends.

    Concrete implementations:
    - :class:`~scraper.backends.requests_backend.RequestsBackend` — pure HTTP
    - :class:`~scraper.backends.playwright_backend.PlaywrightBackend` — JS

    Backends **must** be used as async context managers so that resources
    (connection pools, browser processes) are cleaned up correctly::

        async with PlaywrightBackend() as backend:
            response = await backend.get("https://example.com")
    """

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def __aenter__(self) -> "AbstractBackend":
        await self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def open(self) -> None:
        """Initialise resources (connection pool, browser launch, etc.)."""

    async def close(self) -> None:
        """Release all resources."""

    # ── HTTP primitives ───────────────────────────────────────────────────

    @abstractmethod
    async def get(self, url: str, **kwargs: object) -> PageResponse:
        """Perform an HTTP GET and return a :class:`PageResponse`."""

    @abstractmethod
    async def post(
        self, url: str, data: dict[str, str], **kwargs: object
    ) -> PageResponse:
        """Perform an HTTP POST with form *data* and return a :class:`PageResponse`."""

    # ── Cookie / session helpers ──────────────────────────────────────────

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """Inject cookies into the backend session."""

    def get_cookies(self) -> dict[str, str]:
        """Return all current session cookies."""
        return {}
