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
from services.sentinela_telegram import get_cached_alert, send_alerts_panel
from services.telegram_client import (
    answer_callback_query,
    edit_message_text,
    get_updates,
    is_chat_allowed,
    send_chat_action,
    send_message,
)
from services.telegram_media import (
    default_caption,
    parse_pdf_message,
    parse_photo_message,
)

_STREAMING = os.getenv("TELEGRAM_STREAMING", "1") == "1"
_STREAM_EDIT_CHARS = int(os.getenv("TELEGRAM_STREAM_EDIT_CHARS", "350"))

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
    "/alertas — painel Sentinela com botões Investigar/Parecer\n"
    "Envie PDF → Leitor | Foto → Treino (vision)\n"
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

    if cmd == "/alertas":
        return "__SENTINELA_PANEL__"

    return None


def process_callback_query(hub: AgentHub, callback_query: dict) -> None:
    cq_id = callback_query.get("id")
    data = (callback_query.get("data") or "").strip()
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None or not cq_id:
        return
    if not is_chat_allowed(chat_id):
        logger.warning("Callback de chat não autorizado: %s", chat_id)
        return

    session_id = AgentHub.session_id("telegram", chat_id)
    answer_callback_query(cq_id, "Processando…")

    if ":" not in data:
        return
    action, idx_raw = data.split(":", 1)
    try:
        idx = int(idx_raw)
    except ValueError:
        send_message(chat_id, "Callback inválido.")
        return

    alert = get_cached_alert(chat_id, idx)
    if not alert:
        send_message(chat_id, "Alerta expirado. Use /alertas para recarregar.")
        return

    send_chat_action(chat_id, "typing")
    try:
        if action == "inv":
            reply, agent_used = hub.handoff_investigador(session_id, alert=alert)
        elif action == "par":
            reply, agent_used = hub.handoff_juridico_from_alert(session_id, alert)
        else:
            return
        send_message(chat_id, reply)
        logger.info("callback chat_id=%s action=%s agent=%s", chat_id, action, agent_used)
    except Exception as exc:
        logger.exception("Erro no callback")
        send_message(chat_id, f"Erro: {exc}")


def _dispatch_chat(
    hub: AgentHub,
    chat_id: int | str,
    session_id: str,
    text: str,
    agent_name: str | None = None,
    image_b64: str | None = None,
    preamble: str = "",
) -> None:
    send_chat_action(chat_id, "typing")
    use_stream = _STREAMING and not image_b64

    try:
        if use_stream:
            msg_id = send_message(chat_id, preamble + "🤖 Gerando resposta…")
            last_len = 0

            def on_chunk(acc: str) -> None:
                nonlocal last_len
                if msg_id and len(acc) - last_len >= _STREAM_EDIT_CHARS:
                    edit_message_text(chat_id, msg_id, (preamble + acc)[:4096] or "…")
                    last_len = len(acc)

            reply, agent_used = hub.chat_stream(
                text, session_id, agent_name=agent_name, image_b64=image_b64, on_chunk=on_chunk,
            )
            full = preamble + reply
            if msg_id:
                if len(full) <= 4096:
                    edit_message_text(chat_id, msg_id, full)
                else:
                    edit_message_text(chat_id, msg_id, full[:4096])
                    send_message(chat_id, full[4096:])
            else:
                send_message(chat_id, full)
        else:
            reply, agent_used = hub.chat(
                text, session_id, agent_name=agent_name, image_b64=image_b64,
            )
            send_message(chat_id, preamble + reply)

        logger.info("chat_id=%s agent=%s", chat_id, agent_used)
    except Exception as exc:
        logger.exception("Erro ao processar mensagem")
        send_message(chat_id, f"Erro: {exc}")


def process_update(hub: AgentHub, message: dict) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    if not is_chat_allowed(chat_id):
        logger.warning("Chat não autorizado: %s", chat_id)
        return

    session_id = AgentHub.session_id("telegram", chat_id)

    pdf = parse_pdf_message(message)
    if pdf is not None:
        if pdf.get("error"):
            send_message(chat_id, pdf["error"])
            return
        persist = os.getenv("TELEGRAM_KNOWLEDGE_PERSIST", "0") == "1"
        kb_id, kb_chunks = hub.ingest_pdf_for_session(
            session_id, pdf["text"], pdf["filename"], pdf["pages"], persist=persist,
        )
        preamble = f"📄 {pdf['filename']} ({pdf['pages']} págs)\n"
        if pdf.get("truncated"):
            preamble += "(truncado: 20 primeiras + 5 últimas páginas)\n"
        if kb_id:
            preamble += f"📚 Indexado na base ({kb_chunks} trechos)\n"
        preamble += "\n"
        cap = default_caption(message, "pdf")
        _dispatch_chat(hub, chat_id, session_id, cap, agent_name="leitor", preamble=preamble)
        return

    photo = parse_photo_message(message)
    if photo is not None:
        if photo.get("error"):
            send_message(chat_id, photo["error"])
            return
        hub.set_locked_agent(session_id, "treino")
        cap = default_caption(message, "photo")
        _dispatch_chat(
            hub, chat_id, session_id, cap,
            agent_name="treino", image_b64=photo["image_b64"],
            preamble="📷 Foto recebida\n\n",
        )
        return

    text = (message.get("text") or "").strip()
    if not text:
        send_message(chat_id, "Envie texto, PDF ou foto.")
        return

    if text.startswith("/"):
        reply = handle_command(hub, session_id, text)
        if reply == "__SENTINELA_PANEL__":
            send_alerts_panel(chat_id)
            return
        if reply is not None:
            send_message(chat_id, reply)
            return

    locked = hub.get_locked_agent(session_id)
    _dispatch_chat(hub, chat_id, session_id, text, agent_name=locked)


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
                cb = upd.get("callback_query")
                if cb:
                    process_callback_query(hub, cb)
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
