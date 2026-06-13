"""Pipeline automático Investigador → Jurídico para alertas Sentinela de alta severidade."""

from __future__ import annotations

import hashlib
import logging
import os

from db.database import Database
from services.sentinela_client import SentinelaClient
from services.workflow import start_investigacao_parecer

logger = logging.getLogger("hermes.sentinela_auto")

_MAX_AUTO = int(os.getenv("SENTINELA_AUTO_MAX", "2"))


def alert_key(alert: dict) -> str:
    aid = alert.get("id")
    if aid is not None:
        return f"id:{aid}"
    raw = "|".join(
        str(alert.get(k) or "")
        for k in ("numero_controle_pncp", "fornecedor", "tipo", "descricao")
    )
    return "h:" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def run_auto_workflows(db: Database | None = None, *, notify: bool = False) -> list[str]:
    """Dispara pipeline para alertas alta ainda não processados. Retorna workflow IDs."""
    if os.getenv("SENTINELA_AUTO_WORKFLOW", "1") != "1":
        return []

    db = db or Database()
    client = SentinelaClient()
    resumo = client.get_resumo()
    if resumo.get("offline"):
        return []

    alerts = client.get_alertas(severidade="alta", limit=_MAX_AUTO + 5)
    started: list[str] = []

    for alert in alerts:
        if len(started) >= _MAX_AUTO:
            break
        key = alert_key(alert)
        if db.has_sentinela_auto_workflow(key):
            continue
        wf_id = start_investigacao_parecer(db, alert=alert)
        db.save_sentinela_auto_workflow(key, wf_id, fornecedor=alert.get("fornecedor"))
        started.append(wf_id)
        logger.info("auto workflow %s for alert %s", wf_id, key)

    if notify and started:
        try:
            from cronos.notifier import notify

            names = [a.get("fornecedor", "N/D")[:24] for a in alerts[: len(started)]]
            detail = "\n".join(f"• {n}" for n in names)
            notify(
                f"⚖️ Pipeline automático iniciado ({len(started)} alerta(s) alta severidade):\n{detail}",
                title="Sentinela Auto",
            )
        except Exception as exc:
            logger.warning("notify auto workflow: %s", exc)

    return started
