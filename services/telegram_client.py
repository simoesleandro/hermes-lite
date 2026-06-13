"""Cliente Telegram Bot API (send + long polling)."""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("hermes.telegram")

MAX_MESSAGE_LEN = 4096


def bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def default_chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "")


def allowed_chat_ids() -> set[str]:
    raw = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if raw:
        return {x.strip() for x in raw.split(",") if x.strip()}
    cid = default_chat_id()
    return {cid} if cid else set()


def is_chat_allowed(chat_id: int | str) -> bool:
    allowed = allowed_chat_ids()
    if not allowed:
        logger.warning("Nenhum chat autorizado — configure TELEGRAM_CHAT_ID ou TELEGRAM_ALLOWED_CHAT_IDS")
        return False
    return str(chat_id) in allowed


def _api_post(method: str, payload: dict) -> dict:
    token = bot_token()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram API error"))
    return body


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def send_message(
    chat_id: int | str,
    text: str,
    parse_mode: str | None = None,
    reply_markup: dict | None = None,
) -> int | None:
    """Envia mensagem; retorna message_id do último chunk."""
    chunks = split_message(text)
    last_id: int | None = None
    for i, chunk in enumerate(chunks):
        payload: dict = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        try:
            body = _api_post("sendMessage", payload)
            last_id = body.get("result", {}).get("message_id")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            logger.error("sendMessage falhou: %s — %s", exc, body)
            if parse_mode:
                last_id = send_message(
                    chat_id, chunk, parse_mode=None,
                    reply_markup=reply_markup if i == len(chunks) - 1 else None,
                )
            else:
                raise
    return last_id


def edit_message_text(chat_id: int | str, message_id: int, text: str) -> None:
    payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": text[:MAX_MESSAGE_LEN]}
    try:
        _api_post("editMessageText", payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        if "message is not modified" in body.lower():
            return
        logger.debug("editMessageText: %s — %s", exc, body)


def download_file_bytes(file_id: str) -> bytes:
    """Baixa arquivo do Telegram pelo file_id."""
    token = bot_token()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado")
    meta = _api_post("getFile", {"file_id": file_id})
    file_path = meta.get("result", {}).get("file_path")
    if not file_path:
        raise RuntimeError("file_path ausente em getFile")
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read()


def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
    _api_post("answerCallbackQuery", payload)


def send_chat_action(chat_id: int | str, action: str = "typing") -> None:
    try:
        _api_post("sendChatAction", {"chat_id": chat_id, "action": action})
    except Exception as exc:
        logger.debug("sendChatAction: %s", exc)


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    token = bot_token()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado")
    params: dict[str, str | int] = {
        "timeout": timeout,
        "allowed_updates": json.dumps(["message", "callback_query"]),
    }
    if offset is not None:
        params["offset"] = offset
    qs = urllib.parse.urlencode(params)
    url = f"https://api.telegram.org/bot{token}/getUpdates?{qs}"
    with urllib.request.urlopen(url, timeout=timeout + 10) as resp:
        body = json.loads(resp.read())
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "getUpdates failed"))
    return body.get("result", [])
