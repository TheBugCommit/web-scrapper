"""
portals.run
~~~~~~~~~~~
CLI principal per executar un, diversos o tots els portals de scraping del projecte.

Exemples d'ús:
    python portals/run.py --all
    python portals/run.py messer
    python -m portals.run messer carburos_metalicos
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path so 'portals' and 'scraper' can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portals.config import PortalRegistry

logger = logging.getLogger("portals.run")

# Portals registrats i els seus respectius mòduls de flow
_PORTAL_FLOW_MODULES = {
    "messer": "portals.messer.flow",
    "carburos_metalicos": "portals.carburos_metalicos.flow",
}


async def run_portal(key: str) -> bool:
    """Executa el flux de scraping d'un portal donada la seva clau.

    Retorna True si l'execució ha tingut èxit, False en cas d'error.
    """
    module_name = _PORTAL_FLOW_MODULES.get(key)
    if not module_name:
        print(f"[ERROR] Portal desconegut: '{key}'. Portals disponibles: {list(_PORTAL_FLOW_MODULES.keys())}")
        return False

    print(f"\n>>> Iniciant execució del portal: [{key}]...")
    try:
        mod = importlib.import_module(module_name)
        run_fn = getattr(mod, "run_flow", None)
        if not run_fn or not asyncio.iscoroutinefunction(run_fn):
            print(f"[ERROR] El mòdul {module_name} no defineix una funció asíncrona 'run_flow()'.")
            return False
        await run_fn()
        return True
    except Exception as exc:
        print(f"[ERROR] Error executant el portal [{key}]: {exc}")
        logger.exception("Error en execució de portal %s", key)
        return False


async def main() -> int:
    parser = argparse.ArgumentParser(description="BalfeGo Scraper - CLI de Portals")
    parser.add_argument(
        "portals",
        nargs="*",
        help="Noms dels portals a executar (ex: messer, carburos_metalicos)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Executar tots els portals configurats de manera seqüencial",
    )
    args = parser.parse_args()

    if not args.all and not args.portals:
        parser.print_help()
        print(f"\n[WARN] Portals disponibles: {', '.join(_PORTAL_FLOW_MODULES.keys())}")
        return 1

    target_portals = list(_PORTAL_FLOW_MODULES.keys()) if args.all else args.portals

    registry = PortalRegistry.load()
    success_count = 0
    total = len(target_portals)

    for key in target_portals:
        if key not in _PORTAL_FLOW_MODULES:
            print(f"[ERROR] Portal '{key}' no està registrat a _PORTAL_FLOW_MODULES.")
            continue
        ok = await run_portal(key)
        if ok:
            success_count += 1

    print("\n" + "═" * 60)
    print(f"  Resum d'execució: {success_count}/{total} portals completats amb èxit.")
    print("═" * 60)

    return 0 if success_count == total else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
