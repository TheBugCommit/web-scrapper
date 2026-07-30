"""
scraper.backends.requests_backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure-HTTP backend powered by :mod:`httpx` (async) + :mod:`requests` for
synchronous fallbacks.  Does **not** execute JavaScript — use
:class:`~scraper.backends.playwright_backend.PlaywrightBackend` for JS pages.

Uses :mod:`tenacity` for automatic retries on transient failures.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scraper.backends.base import AbstractBackend, PageResponse
from scraper.utils.logging import get_logger

logger = get_logger(__name__)

_RETRYABLE = (
    httpx.TransportError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
)

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class RequestsBackend(AbstractBackend):
    """Async HTTP backend using :mod:`httpx`.

    Parameters:
        timeout:     Request timeout in seconds.
        max_retries: Maximum retry attempts on transient failures.
        headers:     Additional headers merged with the default header set.
        verify_ssl:  Whether to verify TLS certificates.
        user_agent:  Custom User-Agent string. If ``None``, httpx's own
                     default is used (no hardcoded browser UA).
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
        verify_ssl: bool = True,
        user_agent: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._extra_headers = headers or {}
        self._verify_ssl = verify_ssl
        self._user_agent = user_agent
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        merged_headers = {**DEFAULT_HEADERS}
        if self._user_agent is not None:
            merged_headers["User-Agent"] = self._user_agent
        merged_headers.update(self._extra_headers)
        self._client = httpx.AsyncClient(
            headers=merged_headers,
            timeout=self._timeout,
            follow_redirects=True,
            verify=self._verify_ssl,
        )
        logger.debug("RequestsBackend: client opened")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.debug("RequestsBackend: client closed")

    def _client_or_raise(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "Backend is not open. Use it as an async context manager: "
                "`async with RequestsBackend() as backend: ...`"
            )
        return self._client

    def _make_response(self, r: httpx.Response) -> PageResponse:
        return PageResponse(
            url=str(r.url),
            status_code=r.status_code,
            content=r.text,
            headers=dict(r.headers),
            cookies={k: v for k, v in r.cookies.items()},
        )

    async def get(self, url: str, **kwargs: Any) -> PageResponse:
        """Async GET with automatic retry on transient failures."""
        client = self._client_or_raise()

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async def _get() -> PageResponse:
            logger.debug("GET %s", url)
            r = await client.get(url, **kwargs)
            r.raise_for_status()
            return self._make_response(r)

        return await _get()

    async def post(
        self, url: str, data: dict[str, str], **kwargs: Any
    ) -> PageResponse:
        """Async POST (form-encoded) with automatic retry."""
        client = self._client_or_raise()

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async def _post() -> PageResponse:
            logger.debug("POST %s  data_keys=%s", url, list(data.keys()))
            r = await client.post(url, data=data, **kwargs)
            # Do not raise on 3xx — form logins often redirect
            if r.status_code >= 400:
                r.raise_for_status()
            return self._make_response(r)

        return await _post()

    async def set_cookies(self, cookies: dict[str, str]) -> None:
        client = self._client_or_raise()
        for name, value in cookies.items():
            client.cookies.set(name, value)

    async def get_cookies(self) -> dict[str, str]:
        if self._client is None:
            return {}
        return {name: value for name, value in self._client.cookies.items()}
