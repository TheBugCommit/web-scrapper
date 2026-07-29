"""
scripts/messer.py
~~~~~~~~~~~~~~~~~
Scraper per al portal Global Datacenter (Messer).

La configuració del portal (URLs, selectors) es llegeix de ``portals.yml``.
Les credencials es llegeixen de ``.env.portals`` (gitignored).

Flux d'execució:
  1. PortalRegistry carrega configuració + credencials
  2. Login amb FormAuthHandler generat des del PortalConfig
  3. Navegar al formulari d'exportació XLS
  4. Configurar els paràmetres via FormInteractor (declaratiu)
  5. Submit → descàrrega automàtica de l'arxiu XLS

Per afegir un altre portal: editar portals.yml + .env.portals.
No cal modificar cap script de la llibreria.

Run:
    python scripts/messer.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path so 'portals' package can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper import (
    EventDispatcher,
    ExcelExtractor,
    print_result_summary,
)
from scraper.core.engine import ScraperEngine
from scraper.interaction import (
    CheckboxAction,
    DownloadSubmitAction,
    FormInteractor,
    SelectAction,
    UncheckAllAction,
)
from scraper.utils.logging import configure_logging
from portals.config import PortalConfig, PortalRegistry

registry = PortalRegistry.load()
portal   = registry.get("messer")

DOWNLOAD_DIR = Path("data") / "messer" / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = Path("data") / "messer" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

async def get_last_date(portal: PortalConfig) -> date:
    async with portal.get_repository() as repo:
        return await repo.get_last_date(
            table=portal.db_table or "Telemetria_Tanque_N",
            date_column="timestamp",
            schema=portal.db_schema or "dbo",
            default_date=date(2024, 5, 1),
        )

async def run_flow() -> None:
    configure_logging(log_dir=LOG_DIR, debug=False)
    today = date.today()
    start = await get_last_date(portal)

    print("=" * 60)
    print(f"  {portal.name} - XLS Export")
    print(f"  Portal : {portal.portal_url}")
    print(f"  Dates  : {start.isoformat()} -> {today.isoformat()}")
    print("=" * 60)

    session = (
        portal.get_builder(portal.extra["export_url"])
        .with_download_dir(DOWNLOAD_DIR)
        .with_interaction(
            FormInteractor(
                actions=[
                    # Select module "Balfegó" → page auto-submits and reloads
                    SelectAction(
                        "select[name='modul_id']",
                        value=portal.extra["module_id"],
                        auto_submit=True,
                    ),

                    # Fecha inicio (avui − 2 dies)
                    SelectAction("select[name='startDay']",     str(start.day)),
                    SelectAction("select[name='startMonth']",   str(start.month)),
                    SelectAction("select[name='startYear']",    str(start.year)),
                    SelectAction("select[name='startHour']",    "0"),
                    SelectAction("select[name='startMinute']",  "0"),
                    SelectAction("select[name='startSeconds']", "0"),

                    # Fecha fin (avui)
                    SelectAction("select[name='endDay']",       str(today.day)),
                    SelectAction("select[name='endMonth']",     str(today.month)),
                    SelectAction("select[name='endYear']",      str(today.year)),
                    SelectAction("select[name='endHour']",      "0"),
                    SelectAction("select[name='endMinute']",    "0"),
                    SelectAction("select[name='endSeconds']",   "0"),

                    # Opcions d'exportació
                    SelectAction("select[name='dateTrunc']",        "hour"),  # Elegir fecha → hora
                    SelectAction("select[name='differences']",      "0"),     # Con diferencias → no
                    SelectAction("select[name='ARGOSp']",           "0"),     # Formato Argosp → no
                    SelectAction("select[name='decimalSeparator']", "0"),     # Decimal → coma

                    # Canals: desseleccionar tots, marcar EAN000 + EAN001
                    UncheckAllAction("input[type='checkbox'][name='channelList']"),
                    CheckboxAction("input[name='channelList'][value='EAN000']", checked=True),  # Nivel tanque
                    CheckboxAction("input[name='channelList'][value='EAN001']", checked=True),  # Presion

                    # Submit → descàrrega del fitxer XLS
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

    print_result_summary(result, title=f"{portal.name} - XLS Export")

if __name__ == "__main__":
    asyncio.run(run_flow())
