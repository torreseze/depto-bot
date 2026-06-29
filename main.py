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
    primera_corrida = not seen
    # Fuentes que ya conocíamos (para no inundar cuando se agrega una nueva).
    fuentes_conocidas = {sid.split("-", 1)[0] for sid in seen}
    nuevos = [
        l for l in vigentes
        if l.id not in seen and l.source in fuentes_conocidas
    ]
    # Avisos de una fuente recién agregada: se siembran en silencio (no se notifican).
    sembrados = [
        l for l in vigentes
        if l.id not in seen and l.source not in fuentes_conocidas
    ]
    print(f"[main] {len(nuevos)} nuevos, {len(sembrados)} sembrados en silencio "
          f"(primera_corrida={primera_corrida})")

    # 4) Notificar
    rep = conf.get("reporte", {})
    max_listar = int(rep.get("max_listar", 20))
    fecha = datetime.now(TZ_AR).strftime("%d/%m %H:%M")
    if primera_corrida:
        # Evitamos inundar: resumimos y sembramos el estado.
        messages = notifier.build_first_run_messages(vigentes, fecha, max_listar)
        notifier.send(messages)
    elif nuevos or rep.get("enviar_si_no_hay_nuevos", True):
        messages = notifier.build_messages(nuevos, vigentes, fecha, max_listar)
        notifier.send(messages)
    else:
        print("[main] sin nuevos y reporte deshabilitado, no se envía nada")

    # 5) Persistir estado (marcamos como vistos TODOS los vigentes)
    seen.update(l.id for l in vigentes)
    store.save_seen(seen)
    print("[main] listo")


if __name__ == "__main__":
    main()
