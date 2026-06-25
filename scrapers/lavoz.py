"""Scraper de clasificados.lavoz.com.ar vía su API interna.

La Voz protege su sitio con un WAF que bloquea navegadores automatizados
(Playwright) y peticiones HTTP comunes (403 "Acceso denegado"). La solución es
`curl_cffi`, que imita el fingerprint TLS de Chrome y pasa el filtro.

Endpoint descubierto:
    GET /api/search?page=N&filters=tid:6334 ss_operacion:Alquileres tid_location_should:<id>...
      - tid:6334            -> subcategoría "Departamentos"
      - ss_operacion:Alquileres -> solo alquileres (no venta ni temporarios)
      - tid_location_should:<id> -> barrio (OR entre varios)

Respuesta (JSON):
    data.results.data  -> lista de avisos
    data.results.meta.last_page -> total de páginas
"""
from __future__ import annotations

import time

from curl_cffi import requests

from .base import BaseScraper, Listing

API = "https://clasificados.lavoz.com.ar/api/search"
REFERER = "https://clasificados.lavoz.com.ar/inmuebles/alquileres-departamentos"
HEADERS = {"Accept": "application/json", "Referer": REFERER}

# tid:6334 = Departamentos ; ss_operacion:Alquileres = solo alquiler
BASE_FILTERS = "tid:6334 ss_operacion:Alquileres"

# Mapa de barrio -> id de location (por si querés editar zonas desde el config)
BARRIOS = {
    "Nueva Córdoba": 5034,
    "Centro": 4910,
    "Güemes": 4958,
}


def _parse_price(price: dict):
    """price = {'currency': '$'|'U$S', 'amount': '750.000'} -> (float, 'ARS'|'USD')."""
    if not price:
        return None, None
    cur = (price.get("currency") or "").upper()
    currency = "USD" if "U$S" in cur or "USD" in cur or "US$" in cur else "ARS"
    amount = (price.get("amount") or "").replace(".", "").replace(",", ".")
    try:
        return float(amount), currency
    except ValueError:
        return None, currency


class LaVozScraper(BaseScraper):
    name = "lavoz"

    def _get(self, filters: str, page: int) -> dict:
        last_err = None
        for intento in range(3):
            try:
                r = requests.get(API, params={"page": page, "filters": filters},
                                 headers=HEADERS, impersonate="chrome", timeout=30)
                if r.status_code == 200:
                    return r.json()
                last_err = f"HTTP {r.status_code}"
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
            time.sleep(1.5 * (intento + 1))
        raise RuntimeError(f"[lavoz] fallo al pedir page={page}: {last_err}")

    def fetch(self) -> list[Listing]:
        loc_ids = self.conf.get("location_ids") or list(BARRIOS.values())
        filters = BASE_FILTERS + "".join(f" tid_location_should:{i}" for i in loc_ids)

        # Filtro de dormitorios en el server (valores: "1 Dormitorio",
        # "2 Dormitorios", "3 Dormitorios", "Monoambiente", "4 Dormitorios o más")
        for d in self.conf.get("cantidad_dormitorios") or []:
            filters += f' ss_cantidad_dormitorios:"{d}"'

        max_pag = int(self.conf.get("max_paginas", 0))      # 0 = todas
        hard_cap = int(self.conf.get("hard_cap_paginas", 80))

        out: dict[str, Listing] = {}
        page = 1
        while True:
            data = self._get(filters, page).get("data", {}).get("results", {})
            items = data.get("data", [])
            last_page = data.get("meta", {}).get("last_page", 1) or 1

            for it in items:
                lid = f"lavoz-{it['id']}"
                if lid in out:
                    continue
                price, currency = _parse_price(it.get("price") or {})
                addr = it.get("address") or {}
                out[lid] = Listing(
                    id=lid,
                    source="lavoz",
                    title=(it.get("title") or "").strip(),
                    url=it.get("url", ""),
                    price=price,
                    currency=currency,
                    zona=addr.get("neighborhood"),
                    raw_text=f"{it.get('title','')} {it.get('body','')}",
                )

            limite = last_page if max_pag == 0 else min(max_pag, last_page)
            limite = min(limite, hard_cap)
            print(f"[lavoz] page {page}/{limite} -> {len(items)} avisos "
                  f"(acum {len(out)})")
            if page >= limite or not items:
                break
            page += 1
            time.sleep(0.3)  # cortesía

        return list(out.values())
