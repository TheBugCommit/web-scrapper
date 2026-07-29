"""Unit tests for keyboard keys, KeyCombo builder, and keyboard form actions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from scraper.interaction import FillAction, Key, KeyCombo, PressKeyAction


def test_key_enum_values() -> None:
    assert str(Key.ENTER) == "Enter"
    assert str(Key.TAB) == "Tab"
    assert str(Key.ESCAPE) == "Escape"
    assert str(Key.CONTROL) == "Control"
    assert str(Key.ARROW_DOWN) == "ArrowDown"


def test_keycombo_operator_overloading() -> None:
    combo1 = Key.CONTROL + "a"
    assert str(combo1) == "Control+a"
    assert len(combo1) == 2

    combo2 = Key.CONTROL + Key.SHIFT + Key.ENTER
    assert str(combo2) == "Control+Shift+Enter"
    assert len(combo2) == 3

    combo3 = KeyCombo("Control+a") + Key.DELETE
    assert str(combo3) == "Control+a+Delete"


def test_keycombo_factory_methods() -> None:
    assert str(KeyCombo.ctrl("a")) == "Control+a"
    assert str(KeyCombo.shift(Key.TAB)) == "Shift+Tab"
    assert str(KeyCombo.alt("F4")) == "Alt+F4"
    assert str(KeyCombo.meta("s")) == "Meta+s"
    assert str(KeyCombo.of(Key.CONTROL, Key.SHIFT, "I")) == "Control+Shift+I"


def test_keycombo_from_input() -> None:
    assert KeyCombo.from_input(None) is None
    assert str(KeyCombo.from_input(Key.ENTER)) == "Enter"
    assert str(KeyCombo.from_input("Control+a")) == "Control+a"

    combo = KeyCombo.ctrl("c")
    assert KeyCombo.from_input(combo) is combo


def test_keycombo_equality_and_hashing() -> None:
    c1 = Key.CONTROL + "a"
    c2 = KeyCombo("Control+a")
    assert c1 == c2
    assert c1 == "Control+a"
    assert hash(c1) == hash(c2)


@pytest.mark.asyncio
async def test_fill_action_with_key_enum() -> None:
    page_mock = AsyncMock()
    action = FillAction("input[name='startDate']", "29/07/2026", press_key=Key.ENTER)
    await action.execute(page_mock)

    page_mock.fill.assert_awaited_once_with("input[name='startDate']", "29/07/2026")
    page_mock.press.assert_awaited_once_with("input[name='startDate']", "Enter")


@pytest.mark.asyncio
async def test_fill_action_with_keycombo() -> None:
    page_mock = AsyncMock()
    action = FillAction("input", "value", press_key=Key.CONTROL + "Enter")
    await action.execute(page_mock)

    page_mock.press.assert_awaited_once_with("input", "Control+Enter")


@pytest.mark.asyncio
async def test_press_key_action() -> None:
    page_mock = AsyncMock()
    action = PressKeyAction("input", Key.CONTROL + "a")
    await action.execute(page_mock)

    page_mock.press.assert_awaited_once_with("input", "Control+a")


@pytest.mark.asyncio
async def test_form_interactor_url_pattern_match() -> None:
    from scraper.interaction import FormInteractor
    page_mock = AsyncMock()
    page_mock.url = "https://apdirect.airproducts.com/Tanks/Readings/175738"
    page_mock.content.return_value = "<html>test</html>"

    action_mock = AsyncMock()
    action_mock.downloads = []
    interactor = FormInteractor(actions=[action_mock], url_pattern=r"/Tanks/Readings/")

    result = await interactor.interact(page_mock, context=AsyncMock())
    action_mock.execute.assert_awaited_once_with(page_mock)
    assert result.page_content == "<html>test</html>"


@pytest.mark.asyncio
async def test_form_interactor_url_pattern_skip() -> None:
    from scraper.interaction import FormInteractor
    page_mock = AsyncMock()
    page_mock.url = "https://apdirect.airproducts.com/Tanks/"
    page_mock.content.return_value = "<html>tanks list</html>"

    action_mock = AsyncMock()
    action_mock.downloads = []
    interactor = FormInteractor(actions=[action_mock], url_pattern=r"/Tanks/Readings/")

    result = await interactor.interact(page_mock, context=AsyncMock())
    action_mock.execute.assert_not_called()
    assert result.page_content == "<html>tanks list</html>"
