"""Memória estruturada — fatos persistentes sobre o usuário."""

import re

_REMEMBER_THAT = re.compile(r"^lembrar\s+que\s+(.+)$", re.I)
_REMEMBER_KV = re.compile(r"^lembrar\s+([^=:]+)\s*[=:]\s*(.+)$", re.I)
_FACT_KV = re.compile(r"^fato\s*:\s*([^=:]+)\s*[=:]\s*(.+)$", re.I)
_SAVE = re.compile(r"^guardar\s+fato\s*:\s*(.+)$", re.I)
_LIST = re.compile(r"^(?:listar|mostrar|meus)\s+fatos\b", re.I)
_FORGET = re.compile(r"^(?:esquecer|remover)\s+fato\s+(.+)$", re.I)


def slug_key(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s-]+", "_", s)
    return (s[:60] or "fact").strip("_")


def try_handle_facts(message: str, db) -> str | None:
    """Processa comandos de fatos; retorna resposta imediata ou None."""
    msg = message.strip()
    if not msg:
        return None

    m = _FORGET.match(msg)
    if m:
        fragment = m.group(1).strip()
        fact = db.find_fact(slug_key(fragment)) or db.find_fact(fragment)
        if fact and db.delete_fact(fact["key"]):
            return f"🗑️ Fato removido: «{fact['key']}»"
        return f"⚠️ Fato não encontrado: «{fragment}»"

    if _LIST.match(msg):
        facts = db.list_facts(limit=30)
        if not facts:
            return "Nenhum fato salvo. Use: lembrar que … ou lembrar chave = valor"
        lines = ["📌 Fatos salvos:"]
        for f in facts:
            cat = f" [{f['category']}]" if f.get("category") else ""
            lines.append(f"• {f['key']}{cat}: {f['value']}")
        return "\n".join(lines)

    m = _FACT_KV.match(msg) or _REMEMBER_KV.match(msg)
    if m:
        key = slug_key(m.group(1))
        value = m.group(2).strip()
        db.upsert_fact(key, value)
        return f"✅ Fato salvo: «{key}» = {value}"

    m = _SAVE.match(msg) or _REMEMBER_THAT.match(msg)
    if m:
        value = m.group(1).strip()
        parts = value.split()
        key = slug_key(" ".join(parts[:3])) if parts else "fact"
        db.upsert_fact(key, value)
        return f"✅ Fato salvo: «{key}» → {value}"

    return None
