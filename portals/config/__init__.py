"""
portals.config
~~~~~~~~~~~~~~
Configuration and registry models for portal scraper executions.
"""

from pathlib import Path
from dotenv import load_dotenv

# Automatically load portals/.env when portals.config is imported
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from portals.config.models import PortalConfig
from portals.config.registry import PortalRegistry

__all__ = ["PortalConfig", "PortalRegistry"]
