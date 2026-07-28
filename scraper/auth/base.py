"""
scraper.auth.base
~~~~~~~~~~~~~~~~~
Abstract base class for all authentication handlers.

An auth handler is responsible for bringing the backend session into an
authenticated state **before** the scraping loop starts.  It may perform
any sequence of GET / POST requests, form interactions, or cookie injections.

After :meth:`authenticate` returns successfully the backend's cookie jar /
browser context must contain all session tokens needed for subsequent requests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.backends.base import AbstractBackend
    from scraper.core.context import ScraperContext


class AbstractAuthHandler(ABC):
    """Plugin interface for authentication strategies.

    Implement this class to support a new login mechanism.  Register it
    via :meth:`~scraper.core.builder.ScraperBuilder.with_auth`.

    Example custom handler::

        class MyTokenAuth(AbstractAuthHandler):
            def __init__(self, token: str) -> None:
                self._token = token

            async def authenticate(
                self, backend: AbstractBackend, context: ScraperContext
            ) -> None:
                backend.set_cookies({"auth_token": self._token})
    """

    @abstractmethod
    async def authenticate(
        self, backend: "AbstractBackend", context: "ScraperContext"
    ) -> None:
        """Authenticate against the target portal.

        After this method returns the *backend* session must be ready to
        access authenticated pages.

        Args:
            backend: The live backend instance (already opened).
            context: Shared scraping configuration.

        Raises:
            AuthenticationError: If login fails.
        """


class AuthenticationError(RuntimeError):
    """Raised when an authentication handler fails to log in."""
