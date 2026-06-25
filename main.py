"""Punto de entrada: scrapea, filtra, deduplica y notifica.

Corre una vez por ejecución (pensado para un cron). Ver README.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import yaml

import notifier
import store
from matcher import filter_listings
from scrapers import SCRAPERS

# Córdoba, Argentina = UTC-3
TZ_AR = timezone(timedelta(hours=-3))


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    conf = load_config()
    filtros = conf.get("filtros", {})
    fuentes = conf.get("fuentes", {})

    # 1) Scrapear todas las fuentes habilitadas
    todos: list = []
    for key, fconf in fuentes.items():
        if not fconf or not fconf.get("enabled"):
            continue
        scraper_cls = SCRAPERS.get(key)
        if scraper_cls is None:
            print(f"[main] fuente '{key}' habilitada pero sin scraper implementado, salteando")
            continue
        try:
            res = scraper_cls(fconf).fetch()
            print(f"[main] {key}: {len(res)} avisos crudos")
            todos.extend(res)
        except Exception as e:  # noqa: BLE001
            print(f"[main] error scrapeando {key}: {e}")

    # 2) Filtrar por requisitos
    matches = filter_listings(todos, filtros)
    # dedup por id (por si una fuente repite)
    vigentes = list({l.id: l for l in matches}.values())
    print(f"[main] {len(vigentes)} avisos matchean los filtros")

    # 3) Deduplicar contra lo ya notificado
    seen = store.load_seen()
    nuevos = [l for l in vigentes if l.id not in seen]
    print(f"[main] {len(nuevos)} son nuevos")

    # 4) Notificar
    fecha = datetime.now(TZ_AR).strftime("%d/%m %H:%M")
    if nuevos or conf.get("reporte", {}).get("enviar_si_no_hay_nuevos", True):
        messages = notifier.build_messages(nuevos, vigentes, fecha)
        notifier.send(messages)
    else:
        print("[main] sin nuevos y reporte deshabilitado, no se envía nada")

    # 5) Persistir estado (marcamos como vistos TODOS los vigentes)
    seen.update(l.id for l in vigentes)
    store.save_seen(seen)
    print("[main] listo")


if __name__ == "__main__":
    main()
