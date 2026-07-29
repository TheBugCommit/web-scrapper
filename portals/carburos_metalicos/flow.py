"""
portals/carburos_metalicos.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Scraper per al portal Carburos Metálicos (Air Products).

La configuració del portal (URLs, selectors) es llegeix de ``portals.yml``.
Les credencials es llegeixen de ``.env.portals`` (gitignored).

Flux d'execució:
  1. PortalRegistry carrega configuració + credencials
  2. Login amb FormAuthHandler generat des del PortalConfig
  3. Navegar al link de telemetria /Tanks/Readings/175738
  4. Configurar el filtre de dates en els inputs startDate i endDate via FormInteractor
  5. Descarregar l'arxiu CSV generat via getReadingsCsv
  6. Processar i netejar les columnes CSV convertint dates a zona horaria Europa/Madrid compatible amb SQL Server

Run:
    python portals/carburos_metalicos.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path so 'portals' package can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper import (
    CSVExtractor,
    EventDispatcher,
    print_result_summary,
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
from scraper.utils.logging import configure_logging
from portals.config import PortalConfig, PortalRegistry

registry = PortalRegistry.load()
portal   = registry.get("carburos_metalicos")

DOWNLOAD_DIR = Path("data") / "carburos_metalicos" / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = Path("data") / "carburos_metalicos" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


async def get_last_date(portal: PortalConfig) -> date:
    async with portal.get_repository() as repo:
        return await repo.get_last_date(
            table=portal.db_table or "Telemetria_Tanque_Co2",
            date_column="timestamp",
            schema=portal.db_schema or "dbo",
            default_date=date(2024, 5, 1),
        )


async def run_flow() -> None:
    configure_logging(log_dir=LOG_DIR, debug=False)
    print("=" * 60)
    print("  Carburos Metálicos (Air Products) - Telemetry Scraper")
    print(f"  Portal: {portal.portal_url}")
    print("=" * 60)

    today = date.today()
    start = today - timedelta(days=92)

    print(f"  📅 Rang de dates a escrapejar: {start} -> {today}")
    print("=" * 60)

    session = (
        portal.get_builder()
        .with_download_dir(DOWNLOAD_DIR)
        .with_interaction(
            FormInteractor(
                actions=[
                    # 1. Click Readings link to navigate to /Tanks/Readings/175738
                    ClickAction(
                        "a[href*='/Tanks/Readings/175738']",
                        wait_for_nav=True,
                    ),

                    # 2. Wait for startDate datepicker input to be visible in DOM
                    WaitForAction("input[name='startDate']", timeout=30_000),

                    # 3. Fill startDate (from database last_date or default in dd/mm/yyyy format)
                    FillAction(
                        "input[name='startDate']",
                        f"{start.day}/{start.month}/{start.strftime('%y')}",
                        press_key=Key.ENTER,
                    ),

                    # 4. Fill endDate (today in dd/mm/yyyy format)
                    FillAction(
                        "input[name='endDate']",
                        f"{today.day}/{today.month}/{today.strftime('%y')}",
                        press_key=Key.ENTER,
                    ),

                    
                    ClickAction(
                        "button[type*='submit']",
                        wait_for_nav=False,
                    ),

                    # 5. Wait for download link to appear after Angular updates readings
                    WaitForAction("a[ng-click*='getReadingsCsv']", timeout=30_000),

                    # 6. Click download link to download CSV spreadsheet
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
        .with_storage(portal.get_storage())
        .build()
    )

    dispatcher = EventDispatcher()

    @dispatcher.on("auth.success")
    def on_auth(payload: dict[str, Any]) -> None:
        print("  🔐 [Event: auth.success] Autenticació al portal completada amb èxit!")

    @dispatcher.on("file.downloaded")
    def on_download(payload: dict[str, Any]) -> None:
        print(
            f"  📥 [Event: file.downloaded] Fitxer descarregat: {payload['path']} ({payload['size_bytes']} bytes)"
        )

    @dispatcher.on("storage.saved")
    def on_saved(payload: dict[str, Any]) -> None:
        print(
            f"  🚀 [Event: storage.saved] Desats/upsertats {payload['rows']} registres a SQL Server "
            f"[{payload['schema']}].[{payload['table']}] (PK: {payload['upsert_key']})!"
        )

    @dispatcher.on("storage.skipped")
    def on_skipped(payload: dict[str, Any]) -> None:
        print(
            f"  ⚠️ [Event: storage.skipped] Cap registre per desar a [{payload['schema']}].[{payload['table']}] "
            f"(Motiu: {payload.get('reason')})"
        )

    @dispatcher.on("storage.error")
    def on_error(payload: dict[str, Any]) -> None:
        print(
            f"  ❌ [Event: storage.error] Error desant a [{payload['schema']}].[{payload['table']}]: {payload['error']}"
        )

    engine = ScraperEngine(session, dispatcher=dispatcher)
    result = await engine.run()

    print_result_summary(result, title=f"{portal.name} - CSV Readings Export")


if __name__ == "__main__":
    asyncio.run(run_flow())
