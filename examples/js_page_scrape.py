"""
examples/js_page_scrape.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Scrape a JavaScript-rendered portal using the Playwright backend.

Playwright must be installed:
    pip install playwright
    playwright install chromium

Run:
    python examples/js_page_scrape.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from scraper import ScraperBuilder
from scraper.auth import FormAuthHandler
from scraper.backends import PlaywrightBackend
from scraper.core.context import ScraperContext
from scraper.core.engine import ScraperEngine
from scraper.extractors import CSSExtractor, CSSRule
from scraper.navigation import LinkNavigator

PORTAL_URL = os.getenv("PORTAL_URL", "https://spa.example.com")
LOGIN_URL = os.getenv("LOGIN_URL", f"{PORTAL_URL}/login")


async def main() -> None:
    context = ScraperContext(
        base_url=PORTAL_URL,
        max_concurrent=2,          # lower concurrency for browser-based scraping
        rate_limit_delay=2.0,
        debug_mode=True,
    )

    session = (
        ScraperBuilder()
        .with_context(context)
        .with_url(PORTAL_URL)
        .with_backend(
            PlaywrightBackend(
                browser="chromium",
                headless=True,
                wait_until="networkidle",   # wait for JS to finish loading
            )
        )
        .with_auth(
            FormAuthHandler(
                login_url=LOGIN_URL,
                username=os.getenv("PORTAL_USERNAME", "user"),
                password=os.getenv("PORTAL_PASSWORD", "pass"),
                username_field="input[name=email]",     # CSS selector (Playwright)
                password_field="input[name=password]",
                submit_selector="button[type=submit]",
                success_selector=".app-dashboard",
            )
        )
        .with_navigator(
            LinkNavigator(
                css_filter="nav a, .sidebar a",
                max_links=50,
            )
        )
        .with_extractor(
            CSSExtractor(
                rules={
                    "title": "h1",
                    "table_data": CSSRule("table tbody tr", multiple=True),
                    "last_updated": ".last-updated-date",
                }
            )
        )
        .build()
    )

    engine = ScraperEngine(session)
    result = await engine.run()

    print(f"\n✅ JS scrape complete  pages={len(result.pages)}")
    for page in result.pages[:5]:   # print first 5 for brevity
        print(f"\n  {page.url}")
        print(f"  title: {page.data.get('title')}")


if __name__ == "__main__":
    asyncio.run(main())
