"""scraper.events — lifecycle event system."""

from .cleanup import register_download_cleanup
from .default_handlers import create_default_dispatcher
from .dispatcher import EventDispatcher

__all__ = ["EventDispatcher", "create_default_dispatcher", "register_download_cleanup"]
