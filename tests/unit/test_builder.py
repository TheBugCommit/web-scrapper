"""Unit tests for ScraperBuilder."""

import pytest

from scraper.backends.requests_backend import RequestsBackend
from scraper.core.builder import ScraperBuilder
from scraper.core.session import ScraperSession


def test_build_requires_backend():
    with pytest.raises(ValueError, match="backend"):
        ScraperBuilder().with_url("https://example.com").build()


def test_build_returns_session():
    session = (
        ScraperBuilder()
        .with_url("https://example.com")
        .with_backend(RequestsBackend())
        .build()
    )
    assert isinstance(session, ScraperSession)
    assert session.start_urls == ["https://example.com"]


def test_build_uses_default_context_from_url():
    session = (
        ScraperBuilder()
        .with_url("https://example.com")
        .with_backend(RequestsBackend())
        .build()
    )
    assert session.context.base_url == "https://example.com"


def test_build_multiple_navigators_and_extractors():
    from scraper.extractors import CSSExtractor
    from scraper.navigation import LinkNavigator, PaginationNavigator

    session = (
        ScraperBuilder()
        .with_url("https://example.com")
        .with_backend(RequestsBackend())
        .with_navigator(LinkNavigator())
        .with_navigator(PaginationNavigator())
        .with_extractor(CSSExtractor({"title": "h1"}))
        .with_extractor(CSSExtractor({"price": ".price"}))
        .build()
    )
    assert len(session.navigators) == 2
    assert len(session.extractors) == 2


def test_build_fluent_context_options():
    session = (
        ScraperBuilder()
        .with_url("https://example.com")
        .with_backend(RequestsBackend())
        .with_max_depth(10)
        .with_max_concurrent(8)
        .with_debug_mode(True)
        .with_rate_limit_delay(2.5)
        .with_max_retries(5)
        .with_download_dir("custom_dl")
        .with_headless(False)
        .build()
    )
    assert session.context.max_depth == 10
    assert session.context.max_concurrent == 8
    assert session.context.debug_mode is True
    assert session.context.rate_limit_delay == 2.5
    assert session.context.max_retries == 5
    assert str(session.context.download_dir) == "custom_dl"
    assert session.context.headless is False
