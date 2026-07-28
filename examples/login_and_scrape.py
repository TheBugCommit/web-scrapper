"""
examples/login_and_scrape.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demonstrates form-based login, pagination, CSS extraction, and SQL Server storage.

Requirements:
  - Copy .env.example to .env and set SCRAPER_DB_CONNECTION_STRING
  - Adjust PORTAL_URL, LOGIN_URL, and field selectors for your portal

Run:
    python examples/login_and_scrape.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from scraper import ScraperBuilder
from scraper.auth import FormAuthHandler
from scraper.backends import RequestsBackend
from scraper.core.context import ScraperContext
from scraper.core.engine import ScraperEngine
from scraper.extractors import CSSExtractor
from scraper.navigation import PaginationNavigator
from scraper.storage import SQLServerStorage

# ── Configuration ──────────────────────────────────────────────────────────
# In a real project these come from environment variables / .env
PORTAL_URL = os.getenv("PORTAL_URL", "https://portal.example.com")
LOGIN_URL = os.getenv("LOGIN_URL", f"{PORTAL_URL}/login")
USERNAME = os.getenv("PORTAL_USERNAME", "your_username")
PASSWORD = os.getenv("PORTAL_PASSWORD", "your_password")


async def main() -> None:
    context = ScraperContext(
        base_url=PORTAL_URL,
        max_concurrent=5,
        rate_limit_delay=1.0,
        debug_mode=True,
    )

    session = (
        ScraperBuilder()
        .with_context(context)
        .with_url(PORTAL_URL)
        .with_backend(RequestsBackend(timeout=30.0))
        .with_auth(
            FormAuthHandler(
                login_url=LOGIN_URL,
                username=USERNAME,
                password=PASSWORD,
                username_field="username",     # adjust to the portal's form field names
                password_field="password",
                success_selector=".dashboard",  # CSS element present only when logged in
            )
        )
        .with_navigator(
            PaginationNavigator(
                next_selector="a[rel=next]",
                max_pages=10,
            )
        )
        .with_extractor(
            CSSExtractor(
                rules={
                    "title": "h1.page-title",
                    "record_id": ".record-id",
                    "description": ".record-description",
                }
            )
        )
        .with_storage(SQLServerStorage.from_env())
        .build()
    )

    engine = ScraperEngine(session)
    result = await engine.run()

    print(f"\n✅ Finished  pages={len(result.pages)}  errors={len(result.errors)}")
    print(f"   Duration: {result.duration_seconds:.1f}s")

    if result.errors:
        print("\n⚠️  Errors:")
        for err in result.errors:
            print(f"  {err.url}: {err.error}")


if __name__ == "__main__":
    asyncio.run(main())
