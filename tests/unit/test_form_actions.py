"""Unit tests for form actions (NavigateAction, ClickAction, etc.)."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from scraper.interaction import ClickAction, NavigateAction


@pytest.mark.asyncio
async def test_navigate_action() -> None:
    mock_page = MagicMock()
    mock_page.goto = AsyncMock()

    action = NavigateAction("https://example.com/test", wait_until="load", timeout=15_000)
    await action.execute(mock_page)

    mock_page.goto.assert_called_once_with(
        "https://example.com/test", wait_until="load", timeout=15_000
    )


@pytest.mark.asyncio
async def test_click_action_with_navigation() -> None:
    mock_page = MagicMock()
    mock_page.click = AsyncMock()
    mock_nav_ctx = AsyncMock()
    mock_page.expect_navigation.return_value = mock_nav_ctx

    action = ClickAction("a.my-link", wait_for_nav=True)
    await action.execute(mock_page)

    mock_page.expect_navigation.assert_called_once()
    mock_page.click.assert_called_once_with("a.my-link")
