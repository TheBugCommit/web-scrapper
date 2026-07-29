"""Unit tests for cookie banner dismissal utility."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from scraper.utils.cookies import dismiss_cookie_banners, COOKIE_SELECTORS


@pytest.mark.asyncio
async def test_dismiss_cookie_banners_via_selector() -> None:
    mock_btn = AsyncMock()
    mock_page = MagicMock()
    mock_page.wait_for_selector = AsyncMock(return_value=mock_btn)

    result = await dismiss_cookie_banners(mock_page, timeout_ms=100)

    assert result is True
    mock_page.wait_for_selector.assert_called_once()
    mock_btn.click.assert_called_once_with(timeout=1000)


@pytest.mark.asyncio
async def test_dismiss_cookie_banners_via_text_fallback() -> None:
    mock_page = MagicMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))

    mock_locator = MagicMock()
    mock_locator.is_visible = AsyncMock(return_value=True)
    mock_locator.click = AsyncMock()

    mock_filtered = MagicMock()
    mock_filtered.first = mock_locator
    mock_page.locator.return_value.filter.return_value = mock_filtered

    result = await dismiss_cookie_banners(mock_page, timeout_ms=100)

    assert result is True
    mock_locator.is_visible.assert_called_once()
    mock_locator.click.assert_called_once_with(timeout=1000)


@pytest.mark.asyncio
async def test_dismiss_cookie_banners_none_found() -> None:
    mock_page = MagicMock()
    mock_page.wait_for_selector = AsyncMock(return_value=None)

    mock_locator = MagicMock()
    mock_locator.is_visible = AsyncMock(return_value=False)
    mock_filtered = MagicMock()
    mock_filtered.first = mock_locator
    mock_page.locator.return_value.filter.return_value = mock_filtered

    result = await dismiss_cookie_banners(mock_page, timeout_ms=100)

    assert result is False
