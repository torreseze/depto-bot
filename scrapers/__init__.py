from .base import Listing
from .lavoz import LaVozScraper

# Registro de scrapers disponibles, por clave de config.
SCRAPERS = {
    "lavoz": LaVozScraper,
}

__all__ = ["Listing", "LaVozScraper", "SCRAPERS"]
