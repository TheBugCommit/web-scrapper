"""
scraper.utils.reporting
~~~~~~~~~~~~~~~~~~~~~~~
Reusable formatting and console printing helpers for scraping results.

Usage::

    from scraper import print_result_summary

    result = await engine.run()
    print_result_summary(result, title="Messer Portal Export")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scraper.core.engine import ScrapeResult


def format_result_summary(result: "ScrapeResult", title: str | None = None) -> str:
    """Return a multi-line formatted ASCII summary of a ScrapeResult."""
    lines: list[str] = []

    if title:
        lines.append("=" * 60)
        lines.append(f"  {title}")
        lines.append("=" * 60)

    lines.append(f"  Finished - pages={len(result.pages)}  errors={len(result.errors)}")
    lines.append(f"  Duration: {result.duration_seconds:.1f}s")

    # Collect downloads across all scraped pages
    all_downloads: list[str] = []
    for page in result.pages:
        downloads = page.data.get("_downloads", [])
        if isinstance(downloads, list):
            all_downloads.extend(str(d) for d in downloads)

    if all_downloads:
        lines.append("\n  Downloaded files:")
        for f in all_downloads:
            lines.append(f"    - {f}")

    if result.errors:
        lines.append("\n  Errors:")
        for err in result.errors:
            lines.append(f"    - [{err.url}] {err.error}")

    return "\n".join(lines)


def print_result_summary(result: "ScrapeResult", title: str | None = None) -> None:
    """Print a clean summary of a ScrapeResult to standard output.

    Safe for Windows consoles (uses ASCII characters to avoid cp1252 UnicodeEncodeError).

    Parameters:
        result: The ScrapeResult object returned by ScraperEngine.run().
        title:  Optional header title for the report block.
    """
    print("\n" + format_result_summary(result, title=title))
