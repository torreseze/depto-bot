from .base import Listing
from .lavoz import LaVozScraper
from .argenprop import ArgenpropScraper

# Registro de scrapers disponibles, por clave de config.
SCRAPERS = {
    "lavoz": LaVozScraper,
    "argenprop": ArgenpropScraper,
}

__all__ = ["Listing", "LaVozScraper", "ArgenpropScraper", "SCRAPERS"]
