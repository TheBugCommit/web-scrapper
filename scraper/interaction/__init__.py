"""scraper.interaction — page interaction layer."""

from .actions import (
    CheckboxAction,
    ClickAction,
    DownloadSubmitAction,
    FillAction,
    NavigateAction,
    PressKeyAction,
    SelectAction,
    UncheckAllAction,
    WaitForAction,
)
from .base import AbstractFormAction, AbstractPageInteractor, InteractionResult
from .interactors import FormInteractor
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
