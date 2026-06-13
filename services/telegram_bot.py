"""Bot Telegram bidirecional — long polling + roteamento Hermes."""

import logging
import os
import sys
import time

from dotenv import load_dotenv

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
load_dotenv(os.path.join(_ROOT, ".env"))

from services.agent_hub import AGENT_LABELS, AgentHub
from services.telegram_client import (
    get_updates,
    is_chat_allowed,
    send_chat_action,
    send_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hermes.telegram_bot")

_HELP = (
    "Hermes Lite no Telegram\n\n"
    "Envie uma mensagem — o agente é escolhido automaticamente.\n\n"
    "Comandos:\n"
    "/agente <nome> — fixar agente (ex: saude, sentinela)\n"
    "/auto — roteamento automático\n"
    "/status — agente atual\n"
    "/limpar — apaga histórico da sessão\n"
    "/agentes — lista agentes\n"
    "/help — esta ajuda"
)


def _parse_command(text: str) -> tuple[str, str]:
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    arg = parts[1].strip() if len(parts) > 1 else ""
    return cmd, arg


def handle_command(hub: AgentHub, session_id: str, text: str) -> str | None:
    cmd, arg = _parse_command(text)

    if cmd in ("/start", "/help"):
        return _HELP

    if cmd == "/agentes":
        return "Agentes: " + ", ".join(sorted(AGENT_LABELS.keys()))

    if cmd == "/status":
        locked = hub.get_locked_agent(session_id)
        if locked:
            return f"Agente fixo: {AGENT_LABELS.get(locked, locked)} ({locked})"
        return "Roteamento automático (nenhum agente fixo)"

    if cmd == "/auto":
        hub.set_locked_agent(session_id, None)
        return "Roteamento automático ativado."

    if cmd == "/limpar":
        n = hub.clear_session(session_id)
        return f"Histórico limpo ({n} mensagens removidas)."

    if cmd == "/agente":
        if not arg:
            return "Uso: /agente <nome> — ex: /agente sentinela"
        name = arg.lower().split()[0]
        if name not in hub.agents:
            return "Agente desconhecido. Use /agentes"
        hub.set_locked_agent(session_id, name)
        return f"Agente fixo: {AGENT_LABELS.get(name, name)}"

    return None


def process_update(hub: AgentHub, message: dict) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    if not is_chat_allowed(chat_id):
        logger.warning("Chat não autorizado: %s", chat_id)
        return

    text = (message.get("text") or "").strip()
    if not text:
        send_message(chat_id, "Envie texto. Áudio/imagem ainda não suportados no Telegram.")
        return

    session_id = AgentHub.session_id("telegram", chat_id)

    if text.startswith("/"):
        reply = handle_command(hub, session_id, text)
        if reply is not None:
            send_message(chat_id, reply)
            return

    send_chat_action(chat_id, "typing")
    try:
        locked = hub.get_locked_agent(session_id)
        reply, agent_used = hub.chat(text, session_id, agent_name=locked)
        send_message(chat_id, reply)
        logger.info("chat_id=%s agent=%s len=%s", chat_id, agent_used, len(reply))
    except Exception as exc:
        logger.exception("Erro ao processar mensagem")
        send_message(chat_id, f"Erro: {exc}")


def run_polling(poll_timeout: int = 30) -> None:
    hub = AgentHub()
    offset = None
    logger.info("Telegram bot polling iniciado (timeout=%ss)", poll_timeout)

    while True:
        try:
            updates = get_updates(offset=offset, timeout=poll_timeout)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if msg:
                    process_update(hub, msg)
        except KeyboardInterrupt:
            logger.info("Encerrado pelo usuário")
            break
        except Exception as exc:
            logger.error("Polling error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    if os.getenv("TELEGRAM_BOT_ENABLED", "1") != "1":
        logger.error("TELEGRAM_BOT_ENABLED=0 — bot desligado")
        sys.exit(1)
    run_polling(int(os.getenv("TELEGRAM_POLL_TIMEOUT", "30")))
