"""
scraper.extractors.file_downloader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Extractor that downloads files linked from a page.

Acts as both an :class:`~scraper.extractors.base.AbstractExtractor`
(returns metadata about downloaded files) and performs the actual download
as a side-effect.

Supported link sources:
- ``<a href>`` — downloadable documents, ZIPs, PDFs, etc.
- ``<link href>`` — stylesheets, manifests (opt-in)
- ``<img src>`` — images (opt-in)

Files are saved to the directory configured in
:attr:`~scraper.core.context.ScraperContext.download_dir` (default: ``./downloads``).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse

import aiofiles
import httpx

from scraper.extractors.base import AbstractExtractor
from scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from scraper.backends.base import PageResponse

logger = get_logger(__name__)

# Default file extensions considered downloadable
DEFAULT_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".xml", ".json", ".txt",
}


class FileDownloader(AbstractExtractor):
    """Download files linked from a page and return their metadata.

    Parameters:
        download_dir:   Target directory for downloaded files.
                        Overrides :attr:`~scraper.core.context.ScraperContext.download_dir`.
        extensions:     Set of file extensions to download (include the dot).
                        If *None*, uses :data:`DEFAULT_EXTENSIONS`.
        link_selector:  CSS selector used to find download links.
        url_pattern:    Regex pattern that a link URL must match to be downloaded.
        overwrite:      Re-download even if the file already exists locally.
        max_concurrent: Maximum simultaneous file downloads.
    """

    def __init__(
        self,
        download_dir: str | Path | None = None,
        extensions: set[str] | None = None,
        link_selector: str = "a[href]",
        url_pattern: str | None = None,
        overwrite: bool = False,
        max_concurrent: int = 3,
    ) -> None:
        self._download_dir = Path(download_dir) if download_dir else None
        self._extensions = extensions if extensions is not None else DEFAULT_EXTENSIONS
        self._link_selector = link_selector
        self._url_re = re.compile(url_pattern) if url_pattern else None
        self._overwrite = overwrite
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def extract(self, page: "PageResponse") -> dict[str, Any]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page.content, "lxml")
        download_dir = self._download_dir or Path("./downloads")
        download_dir.mkdir(parents=True, exist_ok=True)

        # Collect candidate URLs
        candidates: list[str] = []
        for tag in soup.select(self._link_selector):
            href: str = tag.get("href", "").strip()
            if not href:
                continue
            # Make absolute
            from scraper.utils.url import normalise
            abs_url = normalise(href, base=page.url)
            ext = Path(urlparse(abs_url).path).suffix.lower()

            if self._extensions and ext not in self._extensions:
                continue
            if self._url_re and not self._url_re.search(abs_url):
                continue
            candidates.append(abs_url)

        if not candidates:
            return {"downloaded_files": []}

        # Download concurrently
        tasks = [self._download(url, download_dir) for url in candidates]
        downloaded = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for url, outcome in zip(candidates, downloaded):
            if isinstance(outcome, Exception):
                logger.warning("FileDownloader: failed %s — %s", url, outcome)
            else:
                results.append(outcome)

        logger.info("FileDownloader: downloaded %d/%d files", len(results), len(candidates))
        return {"downloaded_files": results}

    async def _download(self, url: str, directory: Path) -> dict[str, Any]:
        """Download a single file and return its metadata dict."""
        filename = self._safe_filename(url)
        target = directory / filename

        if target.exists() and not self._overwrite:
            logger.debug("FileDownloader: skipping (exists) %s", filename)
            return {"url": url, "path": str(target), "status": "skipped"}

        async with self._semaphore:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total = 0
                    async with aiofiles.open(target, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            await f.write(chunk)
                            total += len(chunk)

        logger.debug("FileDownloader: saved %s (%d bytes)", filename, total)
        return {"url": url, "path": str(target), "size_bytes": total, "status": "ok"}

    @staticmethod
    def _safe_filename(url: str) -> str:
        """Derive a safe local filename from a URL."""
        path = urlparse(url).path
        name = Path(path).name or hashlib.md5(url.encode()).hexdigest()[:12]
        # Remove unsafe characters
        return re.sub(r'[<>:"/\\|?*]', "_", name)
