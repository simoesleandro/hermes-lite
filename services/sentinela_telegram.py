"""Painel Sentinela no Telegram com InlineKeyboard."""

import logging

from services.sentinela_client import SentinelaClient
from services.telegram_client import default_chat_id, send_message

logger = logging.getLogger("hermes.sentinela_telegram")

_alert_cache: dict[str, list[dict]] = {}


def cache_key(chat_id: int | str) -> str:
    return str(chat_id)


def get_cached_alert(chat_id: int | str, index: int) -> dict | None:
    alerts = _alert_cache.get(cache_key(chat_id), [])
    if 0 <= index < len(alerts):
        return alerts[index]
    return None


def load_alerts(chat_id: int | str, limit: int = 5) -> list[dict]:
    client = SentinelaClient()
    alerts = client.get_alertas(severidade="alta", limit=limit)
    if not alerts:
        alerts = client.get_alertas(limit=limit)
    _alert_cache[cache_key(chat_id)] = alerts
    return alerts


def build_alerts_keyboard(alerts: list[dict]) -> dict | None:
    if not alerts:
        return None
    rows = []
    for i, alert in enumerate(alerts[:3]):
        label = (alert.get("fornecedor") or alert.get("tipo") or f"Alerta {i + 1}")[:18]
        rows.append([
            {"text": f"🔍 {label}", "callback_data": f"inv:{i}"},
            {"text": "⚖️ Parecer", "callback_data": f"par:{i}"},
        ])
    return {"inline_keyboard": rows}


def format_alerts_message(alerts: list[dict], resumo: dict | None = None) -> str:
    lines = ["🔎 Alertas Sentinela"]
    if resumo and not resumo.get("offline"):
        lines.append(f"{resumo.get('alertas_abertos', 0)} abertos · use os botões abaixo")
    if not alerts:
        lines.append("Nenhum alerta crítico no momento.")
        return "\n".join(lines)
    for i, a in enumerate(alerts[:3], 1):
        lines.append(
            f"{i}. {a.get('fornecedor', 'N/D')} — {a.get('tipo', '')} "
            f"({a.get('severidade', '?')})"
        )
    return "\n".join(lines)


def send_alerts_panel(chat_id: int | str | None = None) -> bool:
    cid = chat_id or default_chat_id()
    if not cid:
        return False
    client = SentinelaClient()
    resumo = client.get_resumo()
    if resumo.get("offline"):
        send_message(cid, "Sentinela offline — painel indisponível.")
        return False
    alerts = load_alerts(cid)
    text = format_alerts_message(alerts, resumo)
    keyboard = build_alerts_keyboard(alerts)
    send_message(cid, text, reply_markup=keyboard)
    return True
