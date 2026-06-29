"""Bot interactivo de Telegram (corre en Render, vía webhook).

- Charla un wizard (/configurar) para armar la alarma: precio, dormitorios, zonas.
- Comandos rápidos: /estado, /precio, /dormitorios, /zonas.
- Persiste los filtros en el repo (state/overrides.json) vía la GitHub API, así el
  scraper (GitHub Actions) los toma en la próxima corrida.
- GET / responde para el keep-alive (evita que Render free se duerma).

Variables de entorno requeridas:
  TELEGRAM_BOT_TOKEN   token del bot
  TELEGRAM_CHAT_ID     ids autorizados separados por coma (allowlist)
  WEBHOOK_SECRET       string secreto para la ruta del webhook
  GITHUB_TOKEN         PAT con permiso de escritura en el repo
  GITHUB_REPO          ej "torreseze/depto-bot"
"""
from __future__ import annotations

import base64
import json
import os
import re
import unicodedata

import httpx
from flask import Flask, request

import config_store
import zonas

app = Flask(__name__)

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED = {c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()}
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "hook")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GH_REPO = os.environ.get("GITHUB_REPO", "")

# Filtros vigentes (se cargan del repo al iniciar y se mutan al editar).
CURRENT = config_store.load_config().get("filtros", {})

# Conversaciones en curso: {chat_id: {"step": str, "data": dict}}
SESSIONS: dict[int, dict] = {}

HELP = (
    "🏠 <b>Depto-bot</b>\n"
    "Comandos:\n"
    "• /configurar — armar la alarma paso a paso\n"
    "• /estado — ver los filtros actuales\n"
    "• /precio <i>monto</i> — cambiar precio máximo (ej: /precio 700000)\n"
    "• /dormitorios <i>n[,n]</i> — ej: /dormitorios 1  o  /dormitorios 1,2\n"
    "• /zonas <i>a,b</i> — ej: /zonas Nueva Córdoba, Centro\n"
    "• /cancelar — cancelar la configuración en curso"
)


# Cliente HTTP persistente: reusa la conexión (evita el handshake TLS por mensaje).
_http = httpx.Client(timeout=20, headers={"Connection": "keep-alive"})


# ----------------------------- Telegram I/O -----------------------------
def send(chat_id, text: str) -> None:
    if not TG_TOKEN:
        print(f"[bot] (sin token) -> {chat_id}: {text}")
        return
    try:
        _http.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
        )
    except Exception as e:  # noqa: BLE001
        print(f"[bot] error enviando a {chat_id}: {e}")


# --------------------------- Persistencia (repo) ------------------------
def guardar_filtros() -> bool:
    """Escribe state/overrides.json en el repo vía GitHub API."""
    config_store.save_overrides({"filtros": CURRENT})  # copia local (best-effort)
    if not GH_TOKEN or not GH_REPO:
        print("[bot] sin GITHUB_TOKEN/REPO: guardado solo local")
        return False
    api = f"https://api.github.com/repos/{GH_REPO}/contents/state/overrides.json"
    headers = {"Authorization": f"Bearer {GH_TOKEN}",
               "Accept": "application/vnd.github+json"}
    try:
        r = _http.get(api, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None
        body = json.dumps({"filtros": CURRENT}, ensure_ascii=False, indent=2)
        data = {
            "message": "chore: actualizar filtros desde el bot [skip ci]",
            "content": base64.b64encode(body.encode()).decode(),
            "branch": "main",
        }
        if sha:
            data["sha"] = sha
        r = _http.put(api, headers=headers, json=data)
        return r.status_code in (200, 201)
    except Exception as e:  # noqa: BLE001
        print(f"[bot] error guardando en GitHub: {e}")
        return False


# ------------------------------- Helpers --------------------------------
def estado_text() -> str:
    f = CURRENT
    return (
        "📋 <b>Alarma actual</b>\n"
        f"• Precio máx: ${f.get('precio_max', '-'):,}".replace(",", ".") + "\n"
        f"• Dormitorios: {', '.join(map(str, f.get('dormitorios', []))) or '-'}\n"
        f"• Zonas: {', '.join(f.get('zonas', [])) or '-'}"
    )


def _parse_dorms(text: str):
    nums = re.findall(r"\d+", text)
    return sorted({int(n) for n in nums}) if nums else None


def _parse_zonas(text: str):
    # match contra los nombres conocidos, sin distinguir acentos/mayúsculas
    pedidos = [p.strip() for p in text.split(",") if p.strip()]
    elegidas = []
    for p in pedidos:
        for nombre in zonas.NOMBRES:
            if _norm(p) == _norm(nombre) and nombre not in elegidas:
                elegidas.append(nombre)
    return elegidas


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


# --------------------------- Lógica de comandos -------------------------
def aplicar_y_guardar(chat_id, resumen: str):
    # Confirmamos primero (rápido) y guardamos después; solo avisamos si falla.
    send(chat_id, f"✅ {resumen}\n\n{estado_text()}\n\nLo vas a ver en la próxima corrida.")
    if not guardar_filtros():
        send(chat_id, "⚠️ Ojo: no pude guardar el cambio en GitHub "
                      "(revisá GITHUB_TOKEN/REPO). Reintentá en un rato.")


def handle(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id:
        return
    if ALLOWED and str(chat_id) not in ALLOWED:
        send(chat_id, "🚫 No estás autorizado para configurar este bot.")
        return

    # ¿Wizard en curso y no es un comando?
    if chat_id in SESSIONS and not text.startswith("/"):
        wizard_step(chat_id, text)
        return

    cmd = text.split()[0].lower() if text else ""
    arg = text[len(cmd):].strip()

    if cmd in ("/start", "/ayuda", "/help"):
        send(chat_id, HELP)
    elif cmd == "/estado":
        send(chat_id, estado_text())
    elif cmd == "/configurar":
        SESSIONS[chat_id] = {"step": "precio", "data": {}}
        send(chat_id, "Vamos a armar tu alarma 🏠\n\n1/3 — ¿Precio máximo en pesos? "
                      "(ej: 600000)")
    elif cmd == "/cancelar":
        SESSIONS.pop(chat_id, None)
        send(chat_id, "Listo, cancelado. Tu alarma quedó como estaba.")
    elif cmd == "/precio":
        nums = re.findall(r"\d+", arg)
        if not nums:
            send(chat_id, "Decime el monto, ej: /precio 700000")
        else:
            CURRENT["precio_max"] = int(nums[0])
            aplicar_y_guardar(chat_id, f"Precio máximo: ${int(nums[0]):,}".replace(",", "."))
    elif cmd == "/dormitorios":
        d = _parse_dorms(arg)
        if not d:
            send(chat_id, "Decime las cantidades, ej: /dormitorios 1  o  /dormitorios 1,2")
        else:
            CURRENT["dormitorios"] = d
            aplicar_y_guardar(chat_id, f"Dormitorios: {', '.join(map(str, d))}")
    elif cmd == "/zonas":
        z = _parse_zonas(arg)
        if not z:
            send(chat_id, "No reconocí esas zonas. Disponibles: "
                          + ", ".join(zonas.NOMBRES))
        else:
            CURRENT["zonas"] = z
            aplicar_y_guardar(chat_id, f"Zonas: {', '.join(z)}")
    else:
        send(chat_id, "No entendí 🤔\n\n" + HELP)


def wizard_step(chat_id, text: str) -> None:
    s = SESSIONS[chat_id]
    step, data = s["step"], s["data"]
    if step == "precio":
        nums = re.findall(r"\d+", text)
        if not nums:
            send(chat_id, "Necesito un número, ej: 600000")
            return
        data["precio_max"] = int(nums[0])
        s["step"] = "dormitorios"
        send(chat_id, "2/3 — ¿Cuántos dormitorios? (ej: 1, o 1,2 para 1 y 2)")
    elif step == "dormitorios":
        d = _parse_dorms(text)
        if not d:
            send(chat_id, "Decime números, ej: 1 o 1,2")
            return
        data["dormitorios"] = d
        s["step"] = "zonas"
        send(chat_id, "3/3 — ¿Qué zonas? Disponibles: " + ", ".join(zonas.NOMBRES)
             + "\n(separadas por coma)")
    elif step == "zonas":
        z = _parse_zonas(text)
        if not z:
            send(chat_id, "No reconocí esas zonas. Probá con: " + ", ".join(zonas.NOMBRES))
            return
        data["zonas"] = z
        CURRENT.update(data)
        SESSIONS.pop(chat_id, None)
        aplicar_y_guardar(chat_id, "¡Alarma configurada!")


# -------------------------------- Rutas ---------------------------------
@app.get("/")
def health():
    return "ok", 200


@app.post(f"/webhook/{WEBHOOK_SECRET}")
def webhook():
    try:
        handle(request.get_json(force=True, silent=True) or {})
    except Exception as e:  # noqa: BLE001
        print(f"[bot] error manejando update: {e}")
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
