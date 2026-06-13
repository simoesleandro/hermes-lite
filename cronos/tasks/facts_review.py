"""Task Cronos — lembrete semanal de fatos pendentes (domingo)."""

import os

from db.database import Database
from cronos.notifier import notify


def run() -> None:
    if os.getenv("USER_FACTS", "1") != "1":
        return
    db = Database()
    pending = db.list_facts(status="pending", limit=50)
    if not pending:
        return
    lines = [f"📌 Revisão de memória — {len(pending)} fato(s) pendente(s)", ""]
    for f in pending[:5]:
        lines.append(f"• {f['key']}: {f['value'][:80]}")
    if len(pending) > 5:
        lines.append(f"\n+{len(pending) - 5} no painel Hermes (sidebar → Memória)")
    else:
        lines.append("\nRevise no painel Memória do Hermes Lite.")
    notify("\n".join(lines), title="Fatos pendentes")
