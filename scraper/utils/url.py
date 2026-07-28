"""
scraper.utils.url
~~~~~~~~~~~~~~~~~
URL normalisation, deduplication helpers, and same-origin checks.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse


def normalise(url: str, base: str = "") -> str:
    """Resolve *url* against *base* and strip fragment / trailing slash."""
    resolved = urljoin(base, url) if base else url
    parsed = urlparse(resolved)
    # Drop the fragment (#section) — two URLs differing only in fragment are
    # considered the same page for scraping purposes.
    clean = parsed._replace(fragment="")
    path = clean.path.rstrip("/") or "/"
    return urlunparse(clean._replace(path=path))


def same_origin(url: str, base: str) -> bool:
    """Return *True* if *url* and *base* share the same scheme + netloc."""
    a = urlparse(url)
    b = urlparse(base)
    return a.scheme == b.scheme and a.netloc == b.netloc


def is_navigable(url: str) -> bool:
    """Return *True* for http/https URLs (not mailto:, javascript:, etc.)."""
    scheme = urlparse(url).scheme
    return scheme in ("http", "https")


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract and normalise all ``<a href>`` links from *html*.

    Returns a de-duplicated list of absolute URLs, skipping non-http schemes.
    """
    from bs4 import BeautifulSoup  # local import to avoid circular deps

    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[str] = []

    for tag in soup.find_all("a", href=True):
        href: str = tag["href"].strip()
        if not href or href.startswith("#"):
            continue
        abs_url = normalise(href, base=base_url)
        if is_navigable(abs_url) and abs_url not in seen:
            seen.add(abs_url)
            links.append(abs_url)

    return links
