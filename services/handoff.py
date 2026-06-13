"""Handoff entre agentes — Investigador ↔ Jurídico, Sentinela → Investigador."""


def build_juridico_handoff_message(
    dossier: str,
    sources: list[dict] | None = None,
) -> str:
    """Monta prompt para parecer jurídico a partir de dossiê investigativo."""
    lines = [
        "Emita parecer legal estruturado com base no dossiê investigativo abaixo.",
        "",
        "=== DOSSIÊ INVESTIGATIVO ===",
        dossier.strip(),
    ]
    if sources:
        lines.extend(["", "=== FONTES ==="])
        for s in sources:
            n = s.get("n", "?")
            title = s.get("title", "")
            url = s.get("url")
            line = f"[{n}] {title}"
            if url:
                line += f" — {url}"
            lines.append(line)
    return "\n".join(lines)


def is_juridico_handoff(message: str) -> bool:
    return "=== DOSSIÊ INVESTIGATIVO ===" in message or "=== DOSSIÊ ===" in message


def build_investigador_handoff_message(
    context: str = "",
    alert: dict | None = None,
) -> str:
    """Monta prompt de investigação a partir de alerta Sentinela ou contexto de chat."""
    lines = [
        "Investigar a fundo usando buscar_contratos, buscar_alertas, buscar_cnpj e buscar_web.",
        "Priorize fatos verificáveis e cite fontes.",
        "",
        "=== CONTEXTO SENTINELA ===",
    ]
    if alert:
        for key in ("fornecedor", "tipo", "valor", "severidade", "data", "descricao", "metodologia"):
            val = alert.get(key)
            if val is not None and str(val).strip():
                lines.append(f"{key}: {val}")
    elif context.strip():
        lines.append(context.strip())
    else:
        lines.append("(sem detalhes adicionais)")

    if alert and context.strip():
        lines.extend(["", "=== DETALHES DO CHAT ===", context.strip()])

    return "\n".join(lines)


def is_sentinela_handoff(message: str) -> bool:
    return "=== CONTEXTO SENTINELA ===" in message
