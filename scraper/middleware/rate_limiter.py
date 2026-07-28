"""
scraper.middleware.rate_limiter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Per-host token-bucket rate limiter for the async scraping engine.

The rate limiter enforces a minimum delay between requests **to the same host**
so that the scraper is polite and avoids triggering anti-bot measures.

It is applied automatically by the engine via the ``context.rate_limit_delay``
setting.  For more granular control use :class:`PerHostRateLimiter` directly
inside a custom backend or navigator.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class PerHostRateLimiter:
    """Async per-host rate limiter using a token-bucket-style last-request timestamp.

    Parameters:
        delay: Minimum seconds between requests to the same host.

    Usage::

        limiter = PerHostRateLimiter(delay=2.0)
        await limiter.acquire("https://portal.example.com/page1")
        # ... make request ...
        await limiter.acquire("https://portal.example.com/page2")  # waits if needed
    """

    def __init__(self, delay: float = 1.0) -> None:
        self._delay = delay
        self._last: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, url: str) -> None:
        """Wait (if necessary) before the next request to the host of *url*."""
        from urllib.parse import urlparse
        host = urlparse(url).netloc

        async with self._locks[host]:
            now = time.monotonic()
            elapsed = now - self._last[host]
            wait = self._delay - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[host] = time.monotonic()
