"""Dashboard Home — agrega GTD, Sentinela, Radar, inbox e saúde."""

from __future__ import annotations

import os

from db.database import Database
from services.github_inbox import fetch_github_inbox
from services.sentinela_client import SentinelaClient
from services.syshealth_client import SysHealthClient


def get_dashboard(db: Database | None = None) -> dict:
    db = db or Database()

    tasks_summary = db.tasks_summary()
    tasks_today = db.list_tasks(status="today", limit=6)

    sentinela = SentinelaClient()
    resumo = sentinela.get_resumo()
    alertas: list[dict] = []
    por_sev: dict = {}
    if not resumo.get("offline"):
        alertas = sentinela.get_alertas(limit=4)
        stats = sentinela.get_estatisticas()
        if not stats.get("offline"):
            for row in stats.get("alertas_por_severidade", []):
                por_sev[row.get("severidade", "?")] = row.get("total", 0)

    digest = db.get_latest_github_digest()
    radar_picks = (digest or {}).get("picks") or []
    radar_date = (digest or {}).get("date")

    inbox = fetch_github_inbox()

    sh = SysHealthClient(os.getenv("SYSHEALTH_URL", "http://localhost:5060"))
    health = sh.get_health_summary()

    pending_facts = db.list_facts(status="pending", limit=10)
    workflows = db.list_workflows(limit=5)

    return {
        "gtd": {
            "summary": tasks_summary,
            "today": tasks_today,
        },
        "sentinela": {
            "resumo": resumo,
            "alertas_por_severidade": por_sev,
            "alertas": alertas,
        },
        "radar": {
            "date": radar_date,
            "picks": radar_picks[:4],
        },
        "github_inbox": inbox,
        "health": health,
        "facts_pending": pending_facts,
        "workflows_recent": workflows,
    }
