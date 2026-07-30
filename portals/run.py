"""
portals.run
~~~~~~~~~~~
CLI principal per executar un, diversos o tots els portals de scraping del projecte.

Els portals disponibles es descobreixen automàticament des de ``portals.yml``
(via ``PortalRegistry``) i s'importen per convenció com a ``portals.{key}.flow``
— no cal mantenir cap llista duplicada de mòduls en aquest fitxer.

Quan es demanen diversos portals, s'executen concurrentment (``asyncio.gather``).
Cada portal registra la seva narrativa al seu propi logger (veure
``scraper.utils.logging.get_portal_logger``, usat per cada ``flow.py``), així
que l'execució concurrent no intercala missatges a la consola.

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

from portals.config import PortalRegistry

logger = logging.getLogger("portals.run")


async def run_portal(key: str) -> bool:
    """Executa el flux de scraping d'un portal donada la seva clau.

    Retorna True si l'execució ha tingut èxit, False en cas d'error.
    """
    module_name = f"portals.{key}.flow"

    print(f"\n>>> Iniciant execució del portal: [{key}]...")
    try:
        mod = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        print(
            f"[ERROR] No s'ha pogut importar el mòdul de flow per al portal '{key}' "
            f"(s'esperava {module_name}): {exc}"
        )
        return False

    run_fn = getattr(mod, "run_flow", None)
    if not run_fn or not asyncio.iscoroutinefunction(run_fn):
        print(f"[ERROR] El mòdul {module_name} no defineix una funció asíncrona 'run_flow()'.")
        return False

    try:
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
        help="Executar tots els portals configurats concurrentment",
    )
    args = parser.parse_args()

    registry = PortalRegistry.load()
    available = registry.keys()

    if not args.all and not args.portals:
        parser.print_help()
        print(f"\n[WARN] Portals disponibles: {', '.join(available)}")
        return 1

    target_portals = available if args.all else args.portals

    valid_keys = []
    for key in target_portals:
        if key not in available:
            print(
                f"[ERROR] Portal '{key}' no està registrat a portals.yml. "
                f"Disponibles: {', '.join(available)}"
            )
            continue
        valid_keys.append(key)

    total = len(target_portals)
    results = await asyncio.gather(*(run_portal(key) for key in valid_keys))
    success_count = sum(results)

    print("\n" + "═" * 60)
    print(f"  Resum d'execució: {success_count}/{total} portals completats amb èxit.")
    print("═" * 60)

    return 0 if success_count == total else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
