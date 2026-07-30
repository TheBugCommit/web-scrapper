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


def get_domain(netloc: str) -> str:
    """Return the root domain (e.g. 'airproducts.com' from 'apdirect.airproducts.com')."""
    parts = netloc.split(":")  # drop port if any
    host = parts[0]
    domain_parts = host.split(".")
    if len(domain_parts) >= 2:
        return ".".join(domain_parts[-2:])
    return host


def same_domain(url: str, base: str) -> bool:
    """Return *True* if *url* and *base* share the same root domain (e.g. both *.airproducts.com)."""
    a = urlparse(url)
    b = urlparse(base)
    return a.scheme == b.scheme and get_domain(a.netloc) == get_domain(b.netloc)


def is_navigable(url: str) -> bool:
    """Return *True* for http/https URLs (not mailto:, javascript:, etc.)."""
    scheme = urlparse(url).scheme
    return scheme in ("http", "https")


def extract_links(html: str, base_url: str, selector: str = "a[href]") -> list[str]:
    """Extract and normalise all href-bearing links from *html* matching *selector*.

    Returns a de-duplicated list of absolute URLs, skipping non-http(s) schemes
    and empty/fragment-only hrefs. Shared by navigators, the debug crawler, and
    the file downloader so link-collection logic lives in exactly one place;
    callers apply their own same-origin/same-domain/pattern filters on top.
    """
    from bs4 import BeautifulSoup  # local import to avoid circular deps

    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[str] = []

    for tag in soup.select(selector):
        raw_href = tag.get("href", "")
        href = raw_href[0] if isinstance(raw_href, list) else str(raw_href).strip()
        if not href or href.startswith("#"):
            continue
        abs_url = normalise(href, base=base_url)
        if is_navigable(abs_url) and abs_url not in seen:
            seen.add(abs_url)
            links.append(abs_url)

    return links
