"""Unit tests for CSSExtractor."""

import pytest

from scraper.backends.base import PageResponse
from scraper.extractors.css_extractor import CSSExtractor, CSSRule

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
  <h1 class="page-title">Hello World</h1>
  <p class="price">19,99</p>
  <ul class="tags">
    <li>python</li>
    <li>scraping</li>
    <li>async</li>
  </ul>
  <img src="/hero.jpg" class="hero" />
  <a href="/next" class="next-link">Next</a>
</body>
</html>
"""


def _page(content: str = SAMPLE_HTML) -> PageResponse:
    return PageResponse(url="https://example.com", status_code=200, content=content)


@pytest.mark.asyncio
async def test_extract_text():
    extractor = CSSExtractor(rules={"title": "h1.page-title"})
    result = await extractor.extract(_page())
    assert result["title"] == "Hello World"


@pytest.mark.asyncio
async def test_extract_attribute():
    extractor = CSSExtractor(rules={"img_src": CSSRule("img.hero", attribute="src")})
    result = await extractor.extract(_page())
    assert result["img_src"] == "/hero.jpg"


@pytest.mark.asyncio
async def test_extract_multiple():
    extractor = CSSExtractor(rules={"tags": CSSRule("ul.tags li", multiple=True)})
    result = await extractor.extract(_page())
    assert result["tags"] == ["python", "scraping", "async"]


@pytest.mark.asyncio
async def test_extract_with_transform():
    extractor = CSSExtractor(
        rules={
            "price": CSSRule(
                ".price",
                transform=lambda v: float(v.replace(",", ".")),
            )
        }
    )
    result = await extractor.extract(_page())
    assert result["price"] == pytest.approx(19.99)


@pytest.mark.asyncio
async def test_extract_missing_returns_default():
    extractor = CSSExtractor(rules={"nonexistent": CSSRule(".nonexistent", default="N/A")})
    result = await extractor.extract(_page())
    assert result["nonexistent"] == "N/A"


@pytest.mark.asyncio
async def test_extract_plain_string_selector():
    extractor = CSSExtractor(rules={"title": "title"})
    result = await extractor.extract(_page())
    assert result["title"] == "Test Page"
