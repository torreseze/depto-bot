"""Scraper de argenprop.com vía curl_cffi.

Argenprop renderiza los avisos en el HTML y cada card trae los datos
estructurados como atributos del <a>:
    data-item-card="<id>"  dormitorios="2"  ambientes=""  montooperacion="750000"
    idmoneda="1"(ARS)/"2"(USD)  href="/departamento-en-alquiler-en-<barrio>--<id>"

Particularidades de Argenprop descubiertas:
  - Paginación: ?pagina-N  (con guion, no '=')
  - El slug del barrio solo (ej. /alquiler/nueva-cordoba) filtra bien;
    /alquiler/cordoba/<barrio> significa "Córdoba O <barrio>" (trae toda la ciudad).
  - La zona REAL de cada aviso se saca del href, no del slug buscado, porque las
    búsquedas mezclan barrios (avisos destacados). El matcher después filtra por
    filtros.zonas, así que solo quedan los barrios que te interesan.
"""
from __future__ import annotations

import re
import time

from curl_cffi import requests

from .base import BaseScraper, Listing

BASE = "https://www.argenprop.com"
HEADERS = {"Accept": "text/html", "Accept-Language": "es-AR,es;q=0.9"}

# token de barrio (del href) -> nombre lindo (con acentos) para mostrar y matchear
NICE = {
    "nueva-cordoba": "Nueva Córdoba",
    "centro": "Centro",
    "microcentro": "Centro",
    "guemes": "Güemes",
}

ANCHOR_RE = re.compile(r'<a\s+([^>]*\bdata-item-card="\d+"[^>]*)>', re.S)
BARRIO_RE = re.compile(
    r'/(?:departamento|ph|casa)-en-alquiler-en-([a-z0-9-]+?)(?:-\d+-ambientes?)?--\d+'
)


def _attr(blob: str, name: str):
    m = re.search(rf'\b{name}="([^"]*)"', blob)
    return m.group(1) if m else None


def _zona_de_href(href: str):
    m = BARRIO_RE.search(href)
    if not m:
        return None
    token = m.group(1)
    return NICE.get(token, token.replace("-", " ").title())


class ArgenpropScraper(BaseScraper):
    name = "argenprop"

    def _get(self, url: str) -> str | None:
        for intento in range(3):
            try:
                r = requests.get(url, headers=HEADERS, impersonate="chrome", timeout=30)
                if r.status_code == 200:
                    return r.text
                if r.status_code == 404:
                    return None
            except Exception as e:  # noqa: BLE001
                print(f"[argenprop] error {url}: {e}")
            time.sleep(1.5 * (intento + 1))
        return None

    def _parse(self, html: str, out: dict) -> int:
        nuevos = 0
        for m in ANCHOR_RE.finditer(html):
            blob = m.group(1)
            iid = _attr(blob, "data-item-card")
            href = _attr(blob, "href")
            if not iid or not href:
                continue
            lid = f"argenprop-{iid}"
            if lid in out:
                continue

            dorm = _attr(blob, "dormitorios")
            amb = _attr(blob, "ambientes")
            monto = _attr(blob, "montooperacion")
            moneda = "USD" if _attr(blob, "idmoneda") == "2" else "ARS"
            zona = _zona_de_href(href)
            alt = re.search(r'alt="([^"]+)"', html[m.end():m.end() + 1500])

            out[lid] = Listing(
                id=lid,
                source="argenprop",
                title=(alt.group(1).strip() if alt else href.rsplit("/", 1)[-1]),
                url=BASE + href,
                price=float(monto) if monto and monto.isdigit() else None,
                currency=moneda,
                zona=zona,
                dormitorios=int(dorm) if dorm and dorm.isdigit() else None,
                ambientes=int(amb) if amb and amb.isdigit() else None,
                raw_text=f"{zona or ''}",
            )
            nuevos += 1
        return nuevos

    def fetch(self) -> list[Listing]:
        # slugs de búsqueda (barrio solo). La zona real se saca del href.
        slugs = self.conf.get("slugs") or ["nueva-cordoba", "centro"]
        max_pag = int(self.conf.get("max_paginas", 0))      # 0 = todas
        hard_cap = int(self.conf.get("hard_cap_paginas", 25))

        out: dict[str, Listing] = {}
        for slug in slugs:
            page = 1
            while True:
                url = f"{BASE}/departamentos/alquiler/{slug}"
                if page > 1:
                    url = f"{url}?pagina-{page}"
                html = self._get(url)
                n = self._parse(html, out) if html else 0
                print(f"[argenprop] {slug} p{page} -> {n} nuevos (acum {len(out)})")
                tope = hard_cap if max_pag == 0 else min(max_pag, hard_cap)
                if not html or n == 0 or page >= tope:
                    break
                page += 1
                time.sleep(0.3)
        return list(out.values())
