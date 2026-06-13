import json
import logging
import os
import urllib.error
import urllib.request
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

logger = logging.getLogger("cronos.notifier")


def send_embed(
    webhook_url: str,
    title: str,
    description: str,
    color: int,
    fields: list[dict] = None,
    footer: str = None,
) -> None:
    embed = {"title": title, "description": description, "color": color}
    if fields:
        embed["fields"] = fields
    if footer:
        embed["footer"] = {"text": footer}

    payload = json.dumps({"embeds": [embed]}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "HermesLite/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as exc:
        logger.error("Discord webhook falhou: %s", exc)


def send_telegram(message: str) -> None:
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados")
        return
    payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        logger.error("Telegram notification falhou: %s — %s", exc, body)
    except Exception as exc:
        logger.error("Telegram notification falhou: %s", exc)


def notify(
    message: str,
    title: str = "Hermes Cronos",
    color: int = 0x5865F2,
    discord_webhook: str | None = None,
) -> None:
    """Envia notificação conforme NOTIFY_CHANNEL (telegram|discord|both)."""
    channel = os.getenv("NOTIFY_CHANNEL", "telegram").lower()
    if channel in ("telegram", "both"):
        send_telegram(message)
    if channel in ("discord", "both"):
        webhook = discord_webhook or os.getenv("DISCORD_WEBHOOK_BRIEFING", "") or os.getenv("DISCORD_WEBHOOK_LOGS", "")
        if webhook:
            send_embed(webhook, title, message, color)
        else:
            logger.warning("Discord webhook não configurado para notify()")
