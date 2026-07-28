"""
examples/basic_scrape.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Simplest possible scrape: fetch a public page and extract data via CSS selectors.
No login, no JS, no storage — just print the extracted data.

Run:
    python examples/basic_scrape.py
"""

import asyncio

from scraper import ScraperBuilder
from scraper.backends import RequestsBackend
from scraper.extractors import CSSExtractor


async def main() -> None:
    session = (
        ScraperBuilder()
        .with_url("https://books.toscrape.com")
        .with_backend(RequestsBackend())
        .with_extractor(
            CSSExtractor(
                rules={
                    "page_title": "h1",
                    "book_titles": "article.product_pod h3 a",
                    "prices": "p.price_color",
                }
            )
        )
        .build()
    )

    from scraper.core.engine import ScraperEngine

    engine = ScraperEngine(session)
    result = await engine.run()

    print(f"\n✅ Scraped {len(result.pages)} page(s) in {result.duration_seconds:.1f}s\n")
    for page in result.pages:
        print(f"URL: {page.url}")
        for key, value in page.data.items():
            if not key.startswith("_"):
                print(f"  {key}: {value}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
