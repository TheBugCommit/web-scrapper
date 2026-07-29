"""
scraper.interaction.keys
~~~~~~~~~~~~~~~~~~~~~~~~
Type-safe keyboard key definitions and composable key combination builder
for Playwright-driven form interactions.

Applies Value Object, Factory, and Operator Overloading (Builder) patterns
so key combinations can be constructed expressively without raw magic strings.

Examples::

    # Using enum members directly:
    FillAction("input[name='startDate']", "29/07/2026", press_key=Key.ENTER)
    FillAction("input", "value", press_key=Key.TAB)

    # Combining keys with '+' operator:
    FillAction("input", "value", press_key=Key.CONTROL + "a")
    FillAction("input", "value", press_key=Key.CONTROL + Key.SHIFT + Key.ENTER)

    # Using factory methods:
    FillAction("input", "value", press_key=KeyCombo.ctrl("a"))
    FillAction("input", "value", press_key=KeyCombo.shift(Key.TAB))
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class Key(Enum):
    """Standard Playwright keyboard keys."""

    # Modifiers
    CONTROL = "Control"
    ALT = "Alt"
    SHIFT = "Shift"
    META = "Meta"

    # Action Keys
    ENTER = "Enter"
    TAB = "Tab"
    ESCAPE = "Escape"
    BACKSPACE = "Backspace"
    DELETE = "Delete"
    SPACE = " "

    # Navigation Keys
    ARROW_UP = "ArrowUp"
    ARROW_DOWN = "ArrowDown"
    ARROW_LEFT = "ArrowLeft"
    ARROW_RIGHT = "ArrowRight"
    HOME = "Home"
    END = "End"
    PAGE_UP = "PageUp"
    PAGE_DOWN = "PageDown"

    # Function Keys
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"

    @property
    def value_str(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __add__(self, other: Any) -> "KeyCombo":
        return KeyCombo.of(self, other)

    def __radd__(self, other: Any) -> "KeyCombo":
        return KeyCombo.of(other, self)


class KeyCombo:
    """Value object representing a single key or key combination (e.g. ``"Control+a"``).

    Instances are immutable and composable via the ``+`` operator.
    """

    def __init__(self, *keys: Key | KeyCombo | str) -> None:
        parts: list[str] = []
        for k in keys:
            if isinstance(k, KeyCombo):
                parts.extend(k._keys)
            elif isinstance(k, Key):
                parts.append(k.value)
            elif isinstance(k, str):
                for part in k.split("+"):
                    clean_part = part.strip()
                    if clean_part:
                        parts.append(clean_part)
            else:
                raise TypeError(f"Unsupported key type: {type(k).__name__}")
        self._keys: tuple[str, ...] = tuple(parts)

    @classmethod
    def of(cls, *keys: Key | KeyCombo | str) -> "KeyCombo":
        """Factory method to construct a KeyCombo from one or more keys."""
        return cls(*keys)

    @classmethod
    def ctrl(cls, *keys: Key | KeyCombo | str) -> "KeyCombo":
        """Factory method for Control + key(s)."""
        return cls(Key.CONTROL, *keys)

    @classmethod
    def alt(cls, *keys: Key | KeyCombo | str) -> "KeyCombo":
        """Factory method for Alt + key(s)."""
        return cls(Key.ALT, *keys)

    @classmethod
    def shift(cls, *keys: Key | KeyCombo | str) -> "KeyCombo":
        """Factory method for Shift + key(s)."""
        return cls(Key.SHIFT, *keys)

    @classmethod
    def meta(cls, *keys: Key | KeyCombo | str) -> "KeyCombo":
        """Factory method for Meta + key(s)."""
        return cls(Key.META, *keys)

    @classmethod
    def from_input(cls, val: Key | KeyCombo | str | None) -> "KeyCombo" | None:
        """Convert a polymorphic key input into a KeyCombo instance."""
        if val is None:
            return None
        if isinstance(val, KeyCombo):
            return val
        return cls(val)

    def __add__(self, other: Any) -> "KeyCombo":
        return KeyCombo(self, other)

    def __radd__(self, other: Any) -> "KeyCombo":
        return KeyCombo(other, self)

    def __str__(self) -> str:
        return "+".join(self._keys)

    def __repr__(self) -> str:
        return f"KeyCombo('{self!s}')"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, KeyCombo):
            return self._keys == other._keys
        if isinstance(other, Key):
            return self._keys == (other.value,)
        if isinstance(other, str):
            return str(self) == other
        return False

    def __hash__(self) -> int:
        return hash(self._keys)

    def __len__(self) -> int:
        return len(self._keys)
