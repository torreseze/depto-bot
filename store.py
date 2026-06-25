"""Estado persistente para deduplicar (qué avisos ya notificamos).

Se guarda en state/state.json y el workflow lo commitea de vuelta al repo
después de cada corrida, así la próxima sabe qué ya se avisó.
"""
from __future__ import annotations

import json
import os

STATE_PATH = os.path.join(os.path.dirname(__file__), "state", "state.json")
MAX_SEEN = 3000  # cota para que el archivo no crezca para siempre


def load_seen() -> set[str]:
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data.get("seen", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen: set[str]) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    # Mantenemos solo los últimos MAX_SEEN (orden no garantizado, es best-effort).
    trimmed = list(seen)[-MAX_SEEN:]
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump({"seen": trimmed}, fh, ensure_ascii=False, indent=2)
