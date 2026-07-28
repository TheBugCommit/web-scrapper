"""
scraper.portals.registry
~~~~~~~~~~~~~~~~~~~~~~~~
``PortalRegistry`` — loads portal configs from ``portals.yml`` and merges
credentials from ``.env.portals``.

Design
------
- **portals.yml** (committed to git): portal structure, URLs, field selectors.
  No usernames or passwords.
- **.env.portals** (gitignored): credentials only, one line per portal::

      MESSER_USERNAME=Balfego
      MESSER_PASSWORD=s3cr3t

  Env-var prefix is the portal key in upper-case.  The variables are also
  read from the process environment, so they can be injected via CI/CD
  secrets without a file on disk.

- ``PortalRegistry.load()`` merges both sources into
  :class:`~scraper.portals.config.PortalConfig` instances.

Usage::

    registry = PortalRegistry.load()          # default paths
    portal   = registry.get("messer")

    # Convenience factory builds FormAuthHandler from the config
    auth = portal.form_auth()

    # Portal-specific extras (export URLs, module IDs…) live in portal.extra
    export_url = portal.extra["export_url"]
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from scraper.portals.config import PortalConfig

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG  = "portals.yml"
_DEFAULT_SECRETS = ".env.portals"

# Keys that are handled explicitly — anything else goes into `extra`
_KNOWN_KEYS = frozenset({
    "name", "portal_url", "login_url",
    "username_field", "password_field",
    "success_selector", "headless",
})


class PortalRegistry:
    """Registry of :class:`~scraper.portals.config.PortalConfig` objects.

    Load once at startup, then query by key throughout the application.
    """

    def __init__(self, portals: dict[str, PortalConfig]) -> None:
        self._portals = portals

    # ── Class-level factory ────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        config_path: str | Path = _DEFAULT_CONFIG,
        secrets_path: str | Path = _DEFAULT_SECRETS,
    ) -> "PortalRegistry":
        """Load portals from *config_path* (YAML) and inject credentials from
        *secrets_path* (.env format) or from process environment variables.

        Args:
            config_path:  Path to the YAML portal definitions file.
                          Defaults to ``portals.yml`` in the working directory.
            secrets_path: Path to the ``.env``-style secrets file.
                          Defaults to ``.env.portals`` in the working directory.
                          Missing file is silently ignored — credentials can also
                          come from the process environment directly (useful for
                          Docker / CI/CD).

        Returns:
            A populated :class:`PortalRegistry`.

        Raises:
            FileNotFoundError: If *config_path* does not exist.
            ValueError:        If the YAML is malformed or missing the
                               ``portals:`` top-level key.
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "pyyaml is required for PortalRegistry.  "
                "Install it with: pip install pyyaml"
            ) from exc

        config_path  = Path(config_path)
        secrets_path = Path(secrets_path)

        # ── Load secrets ──────────────────────────────────────────────────────
        secrets: dict[str, str] = {}
        if secrets_path.exists():
            from dotenv import dotenv_values
            secrets = {k: v for k, v in dotenv_values(secrets_path).items() if v}
            logger.debug("PortalRegistry: loaded secrets from %s", secrets_path)
        else:
            logger.debug(
                "PortalRegistry: secrets file %s not found; "
                "falling back to process environment only.",
                secrets_path,
            )

        # ── Load YAML config ──────────────────────────────────────────────────
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

        # ── Build PortalConfig objects ────────────────────────────────────────
        portals: dict[str, PortalConfig] = {}
        for key, cfg in raw["portals"].items():
            if not isinstance(cfg, dict):
                logger.warning("PortalRegistry: skipping %r — not a mapping.", key)
                continue

            prefix   = key.upper()
            username = (
                secrets.get(f"{prefix}_USERNAME")
                or os.environ.get(f"{prefix}_USERNAME", "")
            )
            password = (
                secrets.get(f"{prefix}_PASSWORD")
                or os.environ.get(f"{prefix}_PASSWORD", "")
            )

            if not username or not password:
                logger.warning(
                    "PortalRegistry: portal %r has no credentials. "
                    "Set %s_USERNAME and %s_PASSWORD in .env.portals.",
                    key, prefix, prefix,
                )

            # Split known fields from free-form extras
            known  = {k: v for k, v in cfg.items() if k in _KNOWN_KEYS}
            extras = {k: v for k, v in cfg.items() if k not in _KNOWN_KEYS}

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

    # ── Instance methods ───────────────────────────────────────────────────────

    def get(self, key: str) -> PortalConfig:
        """Return the :class:`~scraper.portals.config.PortalConfig` for *key*.

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
