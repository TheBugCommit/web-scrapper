"""scraper.interaction.actions — concrete AbstractFormAction implementations."""

from .download import DownloadSubmitAction
from .form import CheckboxAction, FillAction, SelectAction, UncheckAllAction
from .navigation import ClickAction, NavigateAction, PressKeyAction, WaitForAction

__all__ = [
    "CheckboxAction",
    "ClickAction",
    "DownloadSubmitAction",
    "FillAction",
    "NavigateAction",
    "PressKeyAction",
    "SelectAction",
    "UncheckAllAction",
    "WaitForAction",
]
