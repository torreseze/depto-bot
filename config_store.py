"""Carga de configuración: config.yaml (defaults) + state/overrides.json (bot).

Los overrides los escribe el bot interactivo (en Render, vía GitHub API). El
scraper y el bot leen ambos y mergean, así el repo es la única fuente de verdad.
"""
from __future__ import annotations

import json
import os

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.yaml")
OVERRIDES_PATH = os.path.join(BASE, "state", "overrides.json")


def load_overrides() -> dict:
    try:
        with open(OVERRIDES_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_overrides(ov: dict) -> None:
    """Escritura local (el bot en Render usa la GitHub API en su lugar)."""
    os.makedirs(os.path.dirname(OVERRIDES_PATH), exist_ok=True)
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as fh:
        json.dump(ov, fh, ensure_ascii=False, indent=2)


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        conf = yaml.safe_load(fh)
    ov = load_overrides()
    for seccion in ("filtros", "reporte"):
        if ov.get(seccion):
            conf[seccion] = {**conf.get(seccion, {}), **ov[seccion]}
    return conf
