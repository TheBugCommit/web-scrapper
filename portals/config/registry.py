"""
portals.config.registry
~~~~~~~~~~~~~~~~~~~~~~~
``PortalRegistry`` — loads portal configs from ``portals.yml`` and merges
credentials from ``portals_credentials.yml``.

Design
------
- **portals.yml** (committed to git): portal structure, URLs, field selectors.
  No usernames or passwords.
- **portals_credentials.yml** (gitignored): credentials per portal::

      messer:
        username: "..."
        password: "..."

- ``PortalRegistry.load()`` merges both sources into
  :class:`~portals.config.models.PortalConfig` instances.

Usage::

    registry = PortalRegistry.load()          # default paths
    portal   = registry.get("messer")

    auth = portal.form_auth()
    export_url = portal.extra["export_url"]
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from portals.config.models import PortalConfig

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG      = "portals/config/portals.yml"
_DEFAULT_CREDENTIALS = "portals/config/portals_credentials.yml"

# Keys that are handled explicitly — anything else goes into `extra`
_KNOWN_KEYS = frozenset({
    "name", "portal_url", "login_url",
    "username_field", "password_field",
    "success_selector",
    "db_table", "db_schema", "db_upsert_key", "db_default_start_date",
})


class PortalRegistry:
    """Registry of :class:`~portals.config.models.PortalConfig` objects.

    Load once at startup, then query by key throughout the application.
    """

    def __init__(self, portals: dict[str, PortalConfig]) -> None:
        self._portals = portals

    @classmethod
    def load(
        cls,
        config_path: str | Path = _DEFAULT_CONFIG,
        credentials_path: str | Path = _DEFAULT_CREDENTIALS,
    ) -> "PortalRegistry":
        """Load portals from *config_path* (YAML) and inject credentials from
        *credentials_path* (YAML).
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "pyyaml is required for PortalRegistry.  "
                "Install it with: pip install pyyaml"
            ) from exc

        config_path      = Path(config_path)
        credentials_path = Path(credentials_path)

        creds_yaml: dict[str, Any] = {}
        if not credentials_path.exists() and Path("portals_credentials.yml").exists():
            credentials_path = Path("portals_credentials.yml")
        if credentials_path.exists():
            with credentials_path.open(encoding="utf-8") as ch:
                creds_yaml = yaml.safe_load(ch) or {}
            logger.debug("PortalRegistry: loaded credentials YAML from %s", credentials_path)

        if not config_path.exists() and Path("portals.yml").exists():
            config_path = Path("portals.yml")
        if not config_path.exists():
            raise FileNotFoundError(
                f"Portal config file not found: {config_path.resolve()}\n"
                "Create 'portals.yml' in the project root.  "
                "See 'portals.yml' for an example."
            )

        with config_path.open(encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}

        if "portals" not in raw:
            raise ValueError(
                f"{config_path} must have a top-level 'portals:' key."
            )

        portals: dict[str, PortalConfig] = {}
        for key, cfg in raw["portals"].items():
            if not isinstance(cfg, dict):
                logger.warning("PortalRegistry: skipping %r — not a mapping.", key)
                continue

            portal_creds = creds_yaml.get(key, {})
            if not isinstance(portal_creds, dict):
                portal_creds = {}

            username = str(portal_creds.get("username", ""))
            password = str(portal_creds.get("password", ""))

            if not username or not password:
                logger.warning(
                    "PortalRegistry: portal %r has missing username/password in %s.",
                    key, credentials_path,
                )

            known  = {k: v for k, v in cfg.items() if k in _KNOWN_KEYS}
            extras = {k: v for k, v in cfg.items() if k not in _KNOWN_KEYS}

            raw_start_date = known.get("db_default_start_date")
            if isinstance(raw_start_date, str):
                known["db_default_start_date"] = date.fromisoformat(raw_start_date)

            # Merge any extra keys defined in portals_credentials.yml into extras
            for k, v in portal_creds.items():
                if k not in ("username", "password") and k not in extras:
                    extras[k] = v

            portals[key] = PortalConfig(
                key=key,
                username=username,
                password=password,
                extra=extras,
                **known,
            )
            logger.debug("PortalRegistry: registered portal %r", key)

        logger.info("PortalRegistry: loaded %d portal(s): %s", len(portals), list(portals))
        return cls(portals)

    def get(self, key: str) -> PortalConfig:
        """Return the :class:`~portals.config.models.PortalConfig` for *key*.

        Args:
            key: Portal identifier as defined in ``portals.yml``.

        Raises:
            KeyError: If *key* is not registered.
        """
        if key not in self._portals:
            available = ", ".join(self._portals) or "(none)"
            raise KeyError(
                f"Portal {key!r} not found in registry.  "
                f"Available portals: {available}"
            )
        return self._portals[key]

    def all(self) -> dict[str, PortalConfig]:
        """Return all registered portals as ``{key: PortalConfig}``."""
        return dict(self._portals)

    def keys(self) -> list[str]:
        """Return the list of registered portal keys."""
        return list(self._portals)

    def __len__(self) -> int:
        return len(self._portals)

    def __repr__(self) -> str:
        return f"PortalRegistry({self.keys()})"
