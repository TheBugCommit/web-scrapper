"""Unit tests for URL utilities."""

import pytest

from scraper.utils.url import extract_links, is_navigable, normalise, same_origin


def test_normalise_strips_fragment():
    assert normalise("https://example.com/page#section") == "https://example.com/page"


def test_normalise_resolves_relative():
    assert normalise("/about", base="https://example.com/home") == "https://example.com/about"


def test_normalise_strips_trailing_slash():
    assert normalise("https://example.com/about/") == "https://example.com/about"


def test_same_origin_true():
    assert same_origin("https://example.com/a", "https://example.com/b") is True


def test_same_origin_false_different_host():
    assert same_origin("https://other.com/a", "https://example.com/a") is False


def test_same_origin_false_different_scheme():
    assert same_origin("http://example.com/a", "https://example.com/a") is False


def test_is_navigable_http():
    assert is_navigable("http://example.com") is True


def test_is_navigable_https():
    assert is_navigable("https://example.com") is True


def test_is_navigable_mailto():
    assert is_navigable("mailto:info@example.com") is False


def test_is_navigable_javascript():
    assert is_navigable("javascript:void(0)") is False


def test_extract_links_returns_absolute():
    html = '<a href="/page1">P1</a> <a href="https://example.com/page2">P2</a>'
    links = extract_links(html, "https://example.com")
    assert "https://example.com/page1" in links
    assert "https://example.com/page2" in links


def test_extract_links_skips_fragments():
    html = '<a href="#top">Top</a>'
    links = extract_links(html, "https://example.com")
    assert links == []


def test_same_domain():
    from scraper.utils.url import same_domain

    assert same_domain("https://apdirect.airproducts.com/Tanks", "https://account.airproducts.com/login") is True
    assert same_domain("https://google.com", "https://account.airproducts.com/login") is False
