"""Extração automática de fatos a partir de mensagens do usuário."""

import json
import logging
import os
import re
import threading

logger = logging.getLogger("hermes.fact_extractor")

_HINT_RE = re.compile(
    r"\b(meta|peso|filho|filha|esposa|marido|fiap|curso|faculdade|"
    r"objetivo|prefiro|moro|trabalho|nasci|anivers|lembro que sou|"
    r"tenho \d+ anos|me chamo|meu nome)\b",
    re.I,
)

_EXTRACT_SYSTEM = (
    "Extraia fatos persistentes sobre o usuário na mensagem abaixo. "
    "Retorne APENAS JSON array: [{\"key\": \"snake_case_curto\", \"value\": \"texto\"}]. "
    "Inclua só fatos estáveis (metas, datas, nomes, preferências, contexto pessoal). "
    "Ignore tarefas, perguntas e pedidos. Se nada relevante, retorne []."
)


def auto_extract_enabled() -> bool:
    return os.getenv("USER_FACTS_AUTO", "0") == "1"


def extract_facts_from_message(message: str) -> list[dict]:
    if not auto_extract_enabled():
        return []
    msg = message.strip()
    if len(msg) < 12 or not _HINT_RE.search(msg):
        return []
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GROQ_API_KEY"):
        return []
    try:
        from model_router import Complexity, get_completion
        raw = get_completion(
            [
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": msg[:800]},
            ],
            Complexity.SIMPLE,
        )
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        out = []
        for item in data[:5]:
            if isinstance(item, dict) and item.get("key") and item.get("value"):
                from services.facts import slug_key
                out.append({
                    "key": slug_key(str(item["key"]))[:60],
                    "value": str(item["value"]).strip()[:500],
                })
        return out
    except Exception as exc:
        logger.debug("fact extract skip: %s", exc)
        return []


def schedule_fact_extraction(message: str, db) -> None:
    if not auto_extract_enabled():
        return

    def _run():
        for fact in extract_facts_from_message(message):
            try:
                db.upsert_fact(fact["key"], fact["value"], category="auto", status="pending")
            except Exception as exc:
                logger.debug("upsert fact: %s", exc)

    threading.Thread(target=_run, daemon=True).start()
