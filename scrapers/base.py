"""Modelo de datos común a todos los scrapers."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Listing:
    """Un aviso normalizado, independiente del portal de origen."""

    id: str                       # id único y estable (idealmente {fuente}-{id_portal})
    source: str                   # "lavoz", "argenprop", etc.
    title: str
    url: str
    price: Optional[float] = None
    currency: Optional[str] = None   # "ARS" | "USD"
    zona: Optional[str] = None
    ambientes: Optional[int] = None
    dormitorios: Optional[int] = None
    m2: Optional[float] = None
    raw_text: str = ""            # texto crudo de la card, para matching por palabras

    def to_dict(self) -> dict:
        return asdict(self)


class BaseScraper:
    """Interfaz que implementa cada scraper de portal."""

    name: str = "base"

    def __init__(self, conf: dict):
        self.conf = conf or {}

    def fetch(self) -> list[Listing]:
        raise NotImplementedError
