"""Filtra avisos según los requisitos del config.

Lo que no viene del scraper (ambientes, dormitorios, m2, zona) se infiere acá
con expresiones regulares sobre el título + texto crudo del aviso.
"""
from __future__ import annotations

import re
import unicodedata

from scrapers.base import Listing


def _norm(s: str) -> str:
    """Minúsculas y sin acentos, para comparar de forma robusta."""
    s = (s or "").lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse_dormitorios(text: str):
    t = _norm(text)
    if re.search(r"mono\s*-?\s*ambiente", t):
        return 0  # un monoambiente no tiene dormitorio separado
    m = re.search(r"(\d+)\s*(dormitorio|dorm\b)", t)
    return int(m.group(1)) if m else None


def parse_ambientes(text: str):
    t = _norm(text)
    if re.search(r"mono\s*-?\s*ambiente", t):
        return 1
    m = re.search(r"(\d+)\s*(ambiente|amb\b)", t)
    return int(m.group(1)) if m else None


def parse_m2(text: str):
    # "60 m2", "60m²", "60 mts2", "60 metros"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(m2|m²|mts2|mts|metros)\b", _norm(text))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _blob(listing: Listing) -> str:
    return f"{listing.title} {listing.raw_text} {listing.zona or ''}"


def enrich(listing: Listing) -> Listing:
    """Completa campos inferidos desde el texto si faltan."""
    blob = _blob(listing)
    if listing.dormitorios is None:
        listing.dormitorios = parse_dormitorios(blob)
    if listing.ambientes is None:
        listing.ambientes = parse_ambientes(blob)
    if listing.m2 is None:
        listing.m2 = parse_m2(blob)
    return listing


def _matches(listing: Listing, f: dict) -> tuple[bool, str]:
    """Devuelve (pasa, motivo_de_descarte)."""
    strict = f.get("strict_unknown", False)
    blob = _norm(_blob(listing))

    # --- palabras excluidas ---
    for w in f.get("excluir_palabras", []):
        if _norm(w) in blob:
            return False, f"excluida por palabra '{w}'"

    # --- moneda + precio ---
    moneda = f.get("moneda", "ARS")
    if listing.currency and listing.currency != moneda:
        return False, f"moneda {listing.currency} != {moneda}"
    if listing.price is None:
        if strict:
            return False, "sin precio"
    else:
        # tolerancia: aceptamos un poco por encima del máximo (deptos al límite)
        tope = f.get("precio_max", float("inf")) + f.get("precio_tolerancia", 0)
        if listing.price > tope:
            return False, f"precio {listing.price:.0f} > max+tol"
        if listing.price < f.get("precio_min", 0):
            return False, f"precio {listing.price:.0f} < min"

    # --- zonas (substring) ---
    zonas = f.get("zonas") or []
    if zonas:
        if not any(_norm(z) in blob for z in zonas):
            return False, "zona no coincide"

    # --- ambientes / dormitorios ---
    amb_min = f.get("ambientes_min")
    if amb_min is not None and listing.ambientes is not None:
        if listing.ambientes < amb_min:
            return False, f"ambientes {listing.ambientes} < {amb_min}"
    elif amb_min is not None and listing.ambientes is None and strict:
        return False, "ambientes desconocidos"

    dorm_min = f.get("dormitorios_min")
    if dorm_min is not None and listing.dormitorios is not None:
        if listing.dormitorios < dorm_min:
            return False, f"dormitorios {listing.dormitorios} < {dorm_min}"
    elif dorm_min is not None and listing.dormitorios is None and strict:
        return False, "dormitorios desconocidos"

    # --- m2 ---
    m2_min = f.get("m2_min")
    if m2_min is not None and listing.m2 is not None:
        if listing.m2 < m2_min:
            return False, f"m2 {listing.m2:.0f} < {m2_min}"
    elif m2_min is not None and listing.m2 is None and strict:
        return False, "m2 desconocidos"

    return True, ""


def filter_listings(listings: list[Listing], filtros: dict) -> list[Listing]:
    out = []
    for l in listings:
        enrich(l)
        ok, reason = _matches(l, filtros)
        if ok:
            out.append(l)
        else:
            print(f"[matcher] descartado {l.id}: {reason}")
    return out
