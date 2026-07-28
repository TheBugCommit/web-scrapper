"""scraper.middleware — cross-cutting concerns (rate limiting, retries)."""

from .rate_limiter import PerHostRateLimiter

__all__ = ["PerHostRateLimiter"]
