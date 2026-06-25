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
    # Orden estable (numérico cuando se puede) para que el diff de git sea mínimo
    # y no haya choques al commitear el estado en cada corrida.
    def _key(x: str):
        n = x.rsplit("-", 1)[-1]
        return (0, int(n)) if n.isdigit() else (1, x)

    ordenado = sorted(seen, key=_key)
    trimmed = ordenado[-MAX_SEEN:]
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump({"seen": trimmed}, fh, ensure_ascii=False, indent=2)
