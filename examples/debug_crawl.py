"""
examples/debug_crawl.py
~~~~~~~~~~~~~~~~~~~~~~~~
Use the DebugCrawler to map all reachable pages from a seed URL.
Outputs a pretty tree to the terminal and saves a JSON crawl map.

Run:
    python examples/debug_crawl.py
    python examples/debug_crawl.py https://example.com --depth 2
"""

import asyncio
import sys

from scraper.backends import RequestsBackend
from scraper.debug import DebugCrawler


async def main(start_url: str = "https://books.toscrape.com", max_depth: int = 2) -> None:
    print(f"\n🕷  Starting debug crawl  seed={start_url}  max_depth={max_depth}\n")

    async with RequestsBackend() as backend:
        crawler = DebugCrawler(
            backend=backend,
            start_url=start_url,
            max_depth=max_depth,
            max_concurrent=5,
        )

        root = await crawler.crawl()

    print("\n📄 Crawl map:\n")
    crawler.print_tree(root)

    all_urls = crawler.all_urls(root)
    print(f"\n📊 Total reachable pages: {len(all_urls)}")

    output_path = "crawl_map.json"
    crawler.export_json(root, output_path)
    print(f"💾 Saved to {output_path}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://books.toscrape.com"
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    asyncio.run(main(url, depth))
