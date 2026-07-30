"""
portals/messer/flow.py
~~~~~~~~~~~~~~~~~~~~~~
Scraper per al portal Global Datacenter (Messer).

La configuració del portal (URLs, selectors) es llegeix de ``portals/config/portals.yml``.
Les credencials es llegeixen de ``portals/config/portals_credentials.yml`` (gitignored).

Flux d'execució:
  1. PortalRegistry carrega configuració + credencials YAML
  2. Inicialitzar ScraperBuilder via ``portal.get_builder(url)`` (amb opcions d'entorn i auth)
  3. Navegar al formulari d'exportació XLS
  4. Configurar els paràmetres via FormInteractor (declaratiu)
  5. Submit → descàrrega automàtica de l'arxiu XLS

Per afegir un altre portal: editar portals.yml + portals_credentials.yml.
No cal modificar cap script de la llibreria scraper.

Run:
    python portals/run.py messer
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path

from scraper import (
    ExcelExtractor,
    create_default_dispatcher,
    format_result_summary,
    print_result_summary,
    register_download_cleanup,
)
from scraper.core.engine import ScraperEngine
from scraper.interaction import (
    CheckboxAction,
    DownloadSubmitAction,
    FormInteractor,
    SelectAction,
    UncheckAllAction,
)
from scraper.utils.logging import get_portal_logger
from portals.config import PortalConfig, PortalRegistry

DOWNLOAD_DIR = Path("data") / "messer" / "downloads"
LOG_DIR = Path("data") / "messer" / "logs"


async def get_last_date(portal: PortalConfig, connection_string: str) -> date:
    async with portal.get_repository(connection_string) as repo:
        return await repo.get_last_date(
            table=portal.db_table or "Telemetria_Tanque_N",
            date_column="timestamp",
            schema=portal.db_schema or "dbo",
            default_date=portal.db_default_start_date or date(2024, 5, 1),
        )


async def run_flow() -> None:
    registry = PortalRegistry.load()
    portal = registry.get("messer")

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = get_portal_logger("messer", LOG_DIR, debug=False)

    connection_string = os.getenv("SCRAPER_DB_CONNECTION_STRING")
    if not connection_string:
        raise RuntimeError(
            "SCRAPER_DB_CONNECTION_STRING is not set in the environment."
        )

    today = date.today()
    start = await get_last_date(portal, connection_string)

    logger.info(
        "%s\n  %s - XLS Export\n  Portal : %s\n  Dates  : %s -> %s\n%s",
        "=" * 60,
        portal.name,
        portal.portal_url,
        start.isoformat(),
        today.isoformat(),
        "=" * 60,
    )

    session = (
        portal.get_builder(portal.extra["export_url"])
        .with_download_dir(DOWNLOAD_DIR)
        .with_interaction(
            FormInteractor(
                actions=[
                    SelectAction(
                        "select[name='modul_id']",
                        value=portal.extra["module_id"],
                        auto_submit=True,
                    ),

                    SelectAction("select[name='startDay']",     str(start.day)),
                    SelectAction("select[name='startMonth']",   str(start.month)),
                    SelectAction("select[name='startYear']",    str(start.year)),
                    SelectAction("select[name='startHour']",    "0"),
                    SelectAction("select[name='startMinute']",  "0"),
                    SelectAction("select[name='startSeconds']", "0"),

                    SelectAction("select[name='endDay']",       str(today.day)),
                    SelectAction("select[name='endMonth']",     str(today.month)),
                    SelectAction("select[name='endYear']",      str(today.year)),
                    SelectAction("select[name='endHour']",      "0"),
                    SelectAction("select[name='endMinute']",    "0"),
                    SelectAction("select[name='endSeconds']",   "0"),

                    SelectAction("select[name='dateTrunc']",        "hour"),  # Elegir fecha → hora
                    SelectAction("select[name='differences']",      "0"),     # Con diferencias → no
                    SelectAction("select[name='ARGOSp']",           "0"),     # Formato Argosp → no
                    SelectAction("select[name='decimalSeparator']", "0"),     # Decimal → coma

                    UncheckAllAction("input[type='checkbox'][name='channelList']"),
                    CheckboxAction("input[name='channelList'][value='EAN000']", checked=True),  # Nivel tanque
                    CheckboxAction("input[name='channelList'][value='EAN001']", checked=True),  # Presion

                    DownloadSubmitAction(
                        selector="input[type='submit'][name='createLink']",
                        download_dir=DOWNLOAD_DIR,
                        timeout=60_000,
                    ),
                ],
                screenshot_on_error=True,
                error_dir=DOWNLOAD_DIR,
            )
        )
        .with_extractor(
            ExcelExtractor(columns=["timestamp", "nivel_tanque_pct", "presion_bar"])
        )
        .with_storage(portal.get_storage(connection_string))
        .build()
    )

    dispatcher = create_default_dispatcher(logger)
    register_download_cleanup(dispatcher, on_events=("storage.saved", "storage.skipped"), logger=logger)

    engine = ScraperEngine(session, dispatcher=dispatcher)
    result = await engine.run()

    title = f"{portal.name} - XLS Export"
    print_result_summary(result, title=title)
    logger.info(format_result_summary(result, title=title))

if __name__ == "__main__":
    asyncio.run(run_flow())
