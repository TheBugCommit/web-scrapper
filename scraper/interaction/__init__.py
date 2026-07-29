"""scraper.interaction — page interaction layer."""

from .base import AbstractFormAction, AbstractPageInteractor, InteractionResult
from .form_actions import (
    CheckboxAction,
    ClickAction,
    DownloadSubmitAction,
    FillAction,
    FormInteractor,
    NavigateAction,
    PressKeyAction,
    SelectAction,
    UncheckAllAction,
    WaitForAction,
)
from .keys import Key, KeyCombo

__all__ = [
    # ABCs
    "AbstractFormAction",
    "AbstractPageInteractor",
    "InteractionResult",
    # Concrete actions
    "SelectAction",
    "CheckboxAction",
    "UncheckAllAction",
    "ClickAction",
    "NavigateAction",
    "FillAction",
    "PressKeyAction",
    "WaitForAction",
    "DownloadSubmitAction",
    # Keys / KeyCombos
    "Key",
    "KeyCombo",
    # Orchestrator
    "FormInteractor",
]
