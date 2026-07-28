"""scraper.interaction — page interaction layer."""

from .base import AbstractFormAction, AbstractPageInteractor, InteractionResult
from .form_actions import (
    CheckboxAction,
    ClickAction,
    DownloadSubmitAction,
    FillAction,
    FormInteractor,
    SelectAction,
    UncheckAllAction,
    WaitForAction,
)

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
    "FillAction",
    "WaitForAction",
    "DownloadSubmitAction",
    # Orchestrator
    "FormInteractor",
]
