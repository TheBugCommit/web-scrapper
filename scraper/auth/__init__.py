"""scraper.auth — authentication handlers."""

from .base import AbstractAuthHandler, AuthenticationError
from .form_auth import FormAuthHandler

__all__ = ["AbstractAuthHandler", "AuthenticationError", "FormAuthHandler"]
