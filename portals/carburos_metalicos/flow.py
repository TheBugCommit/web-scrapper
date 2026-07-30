"""
portals/carburos_metalicos/flow.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Scraper per al portal Carburos Metálicos (Air Products).

La configuració del portal (URLs, selectors) es llegeix de ``portals/config/portals.yml``.
Les credencials es llegeixen de ``portals/config/portals_credentials.yml`` (gitignored).

Flux d'execució:
  1. PortalRegistry carrega configuració + credencials YAML
  2. Login amb FormAuthHandler generat des del PortalConfig via ``portal.get_builder()``
  3. Navegar al link de telemetria /Tanks/Readings/175738
  4. Configurar el filtre de dates en els inputs startDate i endDate via FormInteractor
  5. Descarregar l'arxiu CSV generat via getReadingsCsv
  6. Processar i netejar les columnes CSV convertint dates a zona horaria Europa/Madrid compatible amb SQL Server

Run:
    python portals/run.py carburos_metalicos
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path

from scraper import (
    CSVExtractor,
    create_default_dispatcher,
    format_result_summary,
    print_result_summary,
    register_download_cleanup,
)
from scraper.core.engine import ScraperEngine
from scraper.interaction import (
    ClickAction,
    DownloadSubmitAction,
    FillAction,
    FormInteractor,
    Key,
    WaitForAction,
)
from scraper.utils.logging import get_portal_logger
from portals.config import PortalConfig, PortalRegistry

DOWNLOAD_DIR = Path("data") / "carburos_metalicos" / "downloads"
LOG_DIR = Path("data") / "carburos_metalicos" / "logs"


async def get_last_date(portal: PortalConfig, connection_string: str) -> date:
    async with portal.get_repository(connection_string) as repo:
        return await repo.get_last_date(
            table=portal.db_table or "Telemetria_Tanque_Co2",
            date_column="timestamp",
            schema=portal.db_schema or "dbo",
            default_date=portal.db_default_start_date or date(2024, 5, 1),
        )


async def run_flow() -> None:
    registry = PortalRegistry.load()
    portal = registry.get("carburos_metalicos")

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = get_portal_logger("carburos_metalicos", LOG_DIR, debug=False)

    connection_string = os.getenv("SCRAPER_DB_CONNECTION_STRING")
    if not connection_string:
        raise RuntimeError(
            "SCRAPER_DB_CONNECTION_STRING is not set in the environment."
        )

    today = date.today()
    start = await get_last_date(portal, connection_string)

    logger.info(
        "%s\n  Carburos Metálicos (Air Products) - Telemetry Scraper\n"
        "  Portal: %s\n  📅 Rang de dates a escrapejar: %s -> %s\n%s",
        "=" * 60,
        portal.portal_url,
        start,
        today,
        "=" * 60,
    )

    session = (
        portal.get_builder()
        .with_download_dir(DOWNLOAD_DIR)
        .with_interaction(
            FormInteractor(
                actions=[
                    ClickAction(
                        "a[href*='/Tanks/Readings/175738']",
                        wait_for_nav=True,
                    ),

                    WaitForAction("input[name='startDate']", timeout=30_000),

                    # start is the last stored date (or the portal's configured
                    # fallback), formatted dd/mm/yy as this datepicker expects.
                    FillAction(
                        "input[name='startDate']",
                        f"{start.day}/{start.month}/{start.strftime('%y')}",
                        press_key=Key.ENTER,
                    ),

                    FillAction(
                        "input[name='endDate']",
                        f"{today.day}/{today.month}/{today.strftime('%y')}",
                        press_key=Key.ENTER,
                    ),

                    ClickAction(
                        "button[type*='submit']",
                        wait_for_nav=False,
                    ),

                    # The download link only appears after Angular refreshes the readings list.
                    WaitForAction("a[ng-click*='getReadingsCsv']", timeout=30_000),

                    DownloadSubmitAction(
                        selector="a[ng-click*='getReadingsCsv']",
                        download_dir=DOWNLOAD_DIR,
                        timeout=60_000,
                    ),
                ],
                url_pattern=r"/Tanks/",
                screenshot_on_error=True,
                error_dir=DOWNLOAD_DIR,
            )
        )
        .with_extractor(
            CSVExtractor(
                columns=["nivel_cm", "udm_cm", "peso_kg", "udm_kg", "timestamp", "fuente"],
                clean_comma_decimals=True,
                tz="Europe/Madrid",
            )
        )
        .with_storage(portal.get_storage(connection_string))
        .build()
    )

    dispatcher = create_default_dispatcher(logger)
    register_download_cleanup(dispatcher, logger=logger)

    engine = ScraperEngine(session, dispatcher=dispatcher)
    result = await engine.run()

    title = f"{portal.name} - CSV Readings Export"
    print_result_summary(result, title=title)
    logger.info(format_result_summary(result, title=title))


if __name__ == "__main__":
    asyncio.run(run_flow())
