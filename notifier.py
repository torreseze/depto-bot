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


def _listar(header: str, listings: list[Listing], max_listar: int) -> list[str]:
    mostrados = listings[:max_listar]
    items = [_fmt_listing(l, i + 1) for i, l in enumerate(mostrados)]
    if len(listings) > max_listar:
        items.append(f"… y {len(listings) - max_listar} más.")
    return _chunks(header, items)


def build_first_run_messages(vigentes: list[Listing], fecha: str,
                             max_listar: int = 20) -> list[str]:
    """Primera corrida: no inundamos; resumimos y mostramos algunos ejemplos."""
    if not vigentes:
        return [f"✅ <b>Bot configurado</b> — {fecha}\n"
                f"Por ahora no hay alquileres que matcheen tus filtros. "
                f"Te aviso apenas aparezca alguno."]
    header = (
        f"✅ <b>Bot configurado</b> — {fecha}\n"
        f"Estoy vigilando <b>{len(vigentes)}</b> alquileres que matchean tus filtros. "
        f"De ahora en más te aviso solo cuando aparezca uno nuevo.\n"
        f"Algunos ejemplos de los que ya hay:"
    )
    return _listar(header, vigentes, max_listar)


def build_messages(nuevos: list[Listing], vigentes: list[Listing], fecha: str,
                   max_listar: int = 20) -> list[str]:
    if nuevos:
        header = f"🏠 <b>{len(nuevos)} departamento(s) nuevo(s)</b> — {fecha}"
        return _listar(header, nuevos, max_listar)

    # Sin novedades: avisamos igual y reimprimimos los vigentes (acotados).
    if vigentes:
        header = (
            f"🙃 No encontramos ningún departamento nuevo — {fecha}\n"
            f"Estos son los {len(vigentes)} que matchean tus filtros ahora:"
        )
        return _listar(header, vigentes, max_listar)

    return [f"🙃 No encontramos ningún departamento nuevo — {fecha}\n"
            f"Tampoco hay ninguno que matchee tus filtros por ahora."]


def send(messages: list[str]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids_raw = os.environ.get("TELEGRAM_CHAT_ID", "")
    # Permite varios destinatarios separados por coma: "123,456"
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]
    if not token or not chat_ids:
        print("[notifier] faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. "
              "Mostrando por consola:\n")
        for m in messages:
            print(m, "\n---")
        return

    api = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=30) as client:
        for chat_id in chat_ids:
            for m in messages:
                resp = client.post(api, json={
                    "chat_id": chat_id,
                    "text": m,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                })
                if resp.status_code != 200:
                    print(f"[notifier] error Telegram (chat {chat_id}) "
                          f"{resp.status_code}: {resp.text}")
