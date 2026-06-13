"""Handoff entre agentes — Investigador → Jurídico."""


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
