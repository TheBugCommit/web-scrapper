"""
scraper.utils.cookies
~~~~~~~~~~~~~~~~~~~~~
Generic automatic detection and dismissal of cookie consent banners and GDPR popups.
Supports OneTrust, Cookiebot, Didomi, Quantcast, TrustArc, and generic button patterns.
"""

from __future__ import annotations

from typing import Any

from scraper.utils.logging import get_logger

logger = get_logger(__name__)

# Standard CSS selectors for major consent management platforms (CMPs) and generic cookie banners
COOKIE_SELECTORS = [
    # OneTrust
    "#onetrust-accept-btn-handler",
    "button[id*='onetrust-accept']",
    "#onetrust-banner-sdk button[id*='accept']",
    ".onetrust-close-btn-handler",
    # Cookiebot
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    # Didomi
    "#didomi-notice-agree-button",
    "button[id*='didomi-notice-agree']",
    # Quantcast / Choice
    ".qc-cmp2-summary-buttons button[mode='PRIMARY']",
    ".qc-cmp2-footer button[mode='PRIMARY']",
    # TrustArc / Evidon
    ".truste-button1",
    "#evidon-banner-acceptbutton",
    # Generic IDs, Classes & Attributes (case-insensitive where possible)
    "button[id*='cookie-accept' i]",
    "button[id*='accept-cookies' i]",
    "button[id*='acceptAll' i]",
    "button[id*='accept_all' i]",
    "button[class*='cookie-accept' i]",
    "button[class*='accept-cookies' i]",
    "button[class*='accept-all' i]",
    "#cookie-accept-button",
    ".cookie-accept-button",
    "#accept-all-cookies",
    "#acceptAllCookies",
]

# Common button text patterns in Spanish, Catalan, English, and French
COOKIE_TEXTS = [
    "Aceptar todas las cookies",
    "Aceptar todas",
    "Aceptar todo",
    "Aceptar cookies",
    "Acceptar totes les galetes",
    "Acceptar totes",
    "Acceptar tot",
    "Acceptar galetes",
    "Accept all cookies",
    "Accept all",
    "Accept cookies",
    "Allow all cookies",
    "Allow all",
    "Accepter tout",
    "Accepter toutes les cookies",
]


async def dismiss_cookie_banners(page: Any, timeout_ms: int = 1500) -> bool:
    """Attempt to detect and accept/dismiss cookie consent banners on a Playwright page.

    Returns *True* if a cookie banner was found and clicked, *False* otherwise.
    """
    try:
        combined_selector = ", ".join(COOKIE_SELECTORS)

        # 1. Try standard CMP and generic CSS selectors
        try:
            btn = await page.wait_for_selector(
                combined_selector, state="visible", timeout=timeout_ms
            )
            if btn:
                await btn.click(timeout=1000)
                logger.info("🍪 Dismissed cookie banner via CSS selector")
                return True
        except Exception:
            pass

        # 2. Try text-based fallback search for common accept buttons
        for text in COOKIE_TEXTS:
            try:
                locator = (
                    page.locator("button, a[role='button']").filter(has_text=text).first
                )
                if await locator.is_visible():
                    await locator.click(timeout=1000)
                    logger.info("🍪 Dismissed cookie banner matching text: '%s'", text)
                    return True
            except Exception:
                continue
    except Exception as exc:
        logger.debug("Cookie banner check error: %s", exc)

    return False
