"""Envío de reportes por Telegram."""
from __future__ import annotations

import os

import httpx

from scrapers.base import Listing

TG_LIMIT = 4096  # límite de caracteres por mensaje de Telegram


def _fmt_price(l: Listing) -> str:
    if l.price is None:
        return "precio s/d"
    cur = l.currency or "ARS"
    return f"{'U$S' if cur == 'USD' else '$'} {l.price:,.0f}".replace(",", ".")


def _fmt_listing(l: Listing, idx: int) -> str:
    bits = []
    if l.dormitorios is not None:
        bits.append(f"{l.dormitorios} dorm")
    if l.ambientes is not None:
        bits.append(f"{l.ambientes} amb")
    if l.m2 is not None:
        bits.append(f"{l.m2:.0f}m²")
    meta = " · ".join([_fmt_price(l), *bits])
    title = (l.title or "(sin título)")[:90]
    return f"{idx}. <b>{title}</b>\n   {meta}\n   {l.url}"


def _chunks(header: str, items: list[str]) -> list[str]:
    """Arma mensajes respetando el límite de Telegram."""
    msgs, cur = [], header
    for it in items:
        if len(cur) + len(it) + 2 > TG_LIMIT:
            msgs.append(cur)
            cur = it
        else:
            cur = f"{cur}\n\n{it}" if cur else it
    if cur:
        msgs.append(cur)
    return msgs


def build_messages(nuevos: list[Listing], vigentes: list[Listing], fecha: str) -> list[str]:
    if nuevos:
        header = f"🏠 <b>{len(nuevos)} departamento(s) nuevo(s)</b> — {fecha}"
        items = [_fmt_listing(l, i + 1) for i, l in enumerate(nuevos)]
        return _chunks(header, items)

    # Sin novedades: avisamos igual y reimprimimos los vigentes.
    if vigentes:
        header = (
            f"🙃 No encontramos ningún departamento nuevo — {fecha}\n"
            f"Estos son los {len(vigentes)} que matchean tus filtros ahora:"
        )
        items = [_fmt_listing(l, i + 1) for i, l in enumerate(vigentes)]
        return _chunks(header, items)

    return [f"🙃 No encontramos ningún departamento nuevo — {fecha}\n"
            f"Tampoco hay ninguno que matchee tus filtros por ahora."]


def send(messages: list[str]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[notifier] faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. "
              "Mostrando por consola:\n")
        for m in messages:
            print(m, "\n---")
        return

    api = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=30) as client:
        for m in messages:
            resp = client.post(api, json={
                "chat_id": chat_id,
                "text": m,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            if resp.status_code != 200:
                print(f"[notifier] error Telegram {resp.status_code}: {resp.text}")
