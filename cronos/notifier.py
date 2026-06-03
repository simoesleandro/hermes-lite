import json
import logging
import urllib.request

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
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as exc:
        logger.error("Discord webhook falhou: %s", exc)
