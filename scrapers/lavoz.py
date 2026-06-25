"""Scraper de clasificados.lavoz.com.ar (alquiler de departamentos, Córdoba).

Usa Playwright (navegador real) porque el sitio bloquea peticiones HTTP planas.
Extrae de las páginas de listado: id, url, título y precio. Los demás campos
(ambientes, dormitorios, m2, zona) los infiere el matcher a partir del texto.
"""
from __future__ import annotations

import re

from playwright.sync_api import sync_playwright

from .base import BaseScraper, Listing

# Las URLs de detalle tienen la forma:
#   /avisos/inmuebles/departamento/5625481/algun-slug
DETAIL_RE = re.compile(r"/avisos/inmuebles/[^/]+/(\d+)/")

# JS que corre dentro de la página para juntar avisos.
# Por cada link de detalle único arma {id, url, title, cardText}.
_EXTRACT_JS = r"""
() => {
  const out = {};
  const anchors = Array.from(document.querySelectorAll('a[href*="/avisos/inmuebles/"]'));
  for (const a of anchors) {
    const m = a.getAttribute('href').match(/\/avisos\/inmuebles\/[^/]+\/(\d+)\//);
    if (!m) continue;
    const id = m[1];
    // Subimos hasta un contenedor que tenga precio ($ o U$S).
    let card = a;
    for (let i = 0; i < 6 && card.parentElement; i++) {
      card = card.parentElement;
      if (/\$|U\$S/.test(card.textContent || '')) break;
    }
    const title = (a.textContent || '').trim();
    const cardText = (card.textContent || '').replace(/\s+/g, ' ').trim();
    const prev = out[id];
    // Nos quedamos con el título más largo (suele ser el real, no "Ver más").
    if (!prev || title.length > prev.title.length) {
      out[id] = {
        id,
        url: new URL(a.getAttribute('href'), location.origin).href,
        title: title || (prev ? prev.title : ''),
        cardText,
      };
    } else if (prev && cardText.length > prev.cardText.length) {
      prev.cardText = cardText;
    }
  }
  return Object.values(out);
}
"""

_PRICE_RE = re.compile(r"(U\$S|US\$|USD|\$)\s*([\d.,]+)")


def _parse_price(text: str):
    """Devuelve (monto:float|None, moneda:'ARS'|'USD'|None)."""
    m = _PRICE_RE.search(text or "")
    if not m:
        return None, None
    sym, num = m.group(1), m.group(2)
    currency = "USD" if sym.upper() in ("U$S", "US$", "USD") else "ARS"
    # En es-AR el punto es separador de miles y la coma decimal.
    num = num.replace(".", "").replace(",", ".")
    try:
        return float(num), currency
    except ValueError:
        return None, currency


class LaVozScraper(BaseScraper):
    name = "lavoz"

    def fetch(self) -> list[Listing]:
        urls = self.conf.get("urls", [])
        max_paginas = int(self.conf.get("max_paginas", 1))
        listings: dict[str, Listing] = {}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="es-AR",
                viewport={"width": 1366, "height": 900},
            )
            page = context.new_page()

            for base_url in urls:
                for n in range(1, max_paginas + 1):
                    sep = "&" if "?" in base_url else "?"
                    url = base_url if n == 1 else f"{base_url}{sep}pagina={n}"
                    try:
                        page.goto(url, timeout=45000, wait_until="domcontentloaded")
                        page.wait_for_timeout(2500)  # deja cargar contenido JS
                        rows = page.evaluate(_EXTRACT_JS)
                    except Exception as e:  # noqa: BLE001
                        print(f"[lavoz] error en {url}: {e}")
                        continue

                    nuevos_en_pagina = 0
                    for r in rows:
                        lid = f"lavoz-{r['id']}"
                        if lid in listings:
                            continue
                        price, currency = _parse_price(r.get("cardText", ""))
                        listings[lid] = Listing(
                            id=lid,
                            source="lavoz",
                            title=r.get("title", "").strip(),
                            url=r["url"],
                            price=price,
                            currency=currency,
                            raw_text=r.get("cardText", ""),
                        )
                        nuevos_en_pagina += 1

                    print(f"[lavoz] {url} -> {nuevos_en_pagina} avisos")
                    if nuevos_en_pagina == 0:
                        break  # no hay más páginas

            browser.close()

        return list(listings.values())
