"""Digest matinal unificado — saúde, GTD, Sentinela e Radar GitHub."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from db.database import Database
from services.sentinela_client import SentinelaClient
from services.syshealth_client import SysHealthClient

_TZ = ZoneInfo("America/Sao_Paulo")
_DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _health_block() -> list[str]:
    sh = SysHealthClient(os.getenv("SYSHEALTH_URL", "http://localhost:5060"))
    summary = sh.get_health_summary()
    if summary.get("offline"):
        return ["🎯 Saúde", "SysHealth offline"]

    agua = summary.get("agua_hoje_ml") or 0
    prot = summary.get("proteina_g")
    prot_txt = f"{prot}g" if prot is not None else "—"
    falta_agua = max(0, 3000 - agua)
    treinos = sh.get_treinos_recentes(dias=1)
    if treinos:
        agenda = treinos[0].get("descricao") or treinos[0].get("tipo") or "Treino registrado"
    else:
        agenda = "Dia de descanso"

    return [
        "🎯 Saúde",
        f"Água: {agua}/3000 ml (faltam {falta_agua}) · Proteína: {prot_txt}/190g",
        f"Treino: {agenda}",
    ]


def _gtd_block(db: Database) -> list[str]:
    today = db.list_tasks(status="today", limit=8)
    inbox = db.list_tasks(status="inbox", limit=50)
    week = db.list_tasks(status="week", limit=50)
    lines = ["📋 GTD"]
    if not today:
        lines.append("Hoje: nenhuma tarefa")
    else:
        lines.append(f"Hoje ({len(today)}):")
        for t in today[:5]:
            mark = "🔴" if t.get("priority") == "high" else "•"
            lines.append(f"  {mark} {t['title'][:60]}")
        if len(today) > 5:
            lines.append(f"  +{len(today) - 5}…")
    if inbox:
        lines.append(f"Inbox: {len(inbox)} pendente(s)")
    if week:
        lines.append(f"Semana: {len(week)} tarefa(s)")
    return lines


def _sentinela_block() -> tuple[list[str], dict, list[dict]]:
    resumo = SentinelaClient().get_resumo()
    if resumo.get("offline"):
        return (["🔎 Sentinela", "Offline"], resumo, [])

    alerts = SentinelaClient().get_alertas(severidade="alta", limit=3)
    if not alerts:
        alerts = SentinelaClient().get_alertas(limit=3)

    lines = [
        "🔎 Sentinela",
        f"{resumo.get('alertas_abertos', 0)} alertas abertos",
    ]
    for i, a in enumerate(alerts[:3], 1):
        lines.append(
            f"  {i}. {a.get('fornecedor', 'N/D')[:28]} — {a.get('tipo', '')} "
            f"({a.get('severidade', '?')})"
        )
    return lines, resumo, alerts


def _radar_block(db: Database, date_str: str) -> list[str]:
    digest = db.get_github_digest_by_date(date_str)
    if not digest:
        digest = db.get_latest_github_digest()
    picks = (digest or {}).get("picks") or []
    lines = ["📡 Radar GitHub"]
    if not picks:
        lines.append("Sem curadoria hoje (Radar desativado ou sem picks)")
        return lines
    for p in picks[:3]:
        lines.append(f"  • {p.get('full_name')} ({p.get('nota', 0)}/10)")
        oq = (p.get("o_que_faz") or "")[:80]
        if oq:
            lines.append(f"    {oq}")
    if len(picks) > 3:
        lines.append(f"  +{len(picks) - 3} no export MD")
    return lines


def _github_inbox_block() -> list[str]:
    if os.getenv("GITHUB_INBOX_ENABLED", "1") != "1":
        return []
    try:
        from services.github_inbox import build_inbox_lines

        return ["", *build_inbox_lines()]
    except Exception:
        return ["", "🐙 GitHub", "Inbox indisponível"]


def build_morning_message(db: Database | None = None) -> str:
    db = db or Database()
    agora = datetime.now(_TZ)
    date_str = agora.strftime("%Y-%m-%d")
    data_fmt = agora.strftime("%d/%m/%Y")
    dia_semana = _DIAS_PT[agora.weekday()]

    parts = [
        f"☀️ Bom dia — {data_fmt} · {dia_semana}",
        "",
        *_health_block(),
        "",
        *_gtd_block(db),
        "",
    ]
    sent_lines, _, _ = _sentinela_block()
    parts.extend(sent_lines)
    parts.extend(_github_inbox_block())
    parts.extend(["", *_radar_block(db, date_str), "", "Hermes · digest matinal"])
    return "\n".join(parts)


def run_morning_digest(*, notify: bool = True, db: Database | None = None) -> dict:
    """Executa Radar (se necessário), monta digest e notifica."""
    if os.getenv("MORNING_DIGEST_ENABLED", "1") != "1":
        return {"skipped": True, "reason": "MORNING_DIGEST_ENABLED=0"}

    db = db or Database()
    agora = datetime.now(_TZ)
    date_str = agora.strftime("%Y-%m-%d")

    radar_result: dict = {}
    if os.getenv("GITHUB_RADAR_ENABLED", "1") == "1":
        from services.github_radar import run_github_radar

        radar_result = run_github_radar(db, notify=False)

    message = build_morning_message(db)

    if notify:
        from cronos.notifier import notify

        notify(message, title="Digest matinal", discord_webhook=os.getenv("DISCORD_WEBHOOK_BRIEFING"))

    resumo = SentinelaClient().get_resumo()
    if notify and not resumo.get("offline") and resumo.get("alertas_abertos", 0) > 0:
        try:
            from services.sentinela_telegram import send_alerts_panel

            send_alerts_panel()
        except Exception:
            pass

    auto_started: list[str] = []
    if os.getenv("SENTINELA_AUTO_WORKFLOW", "1") == "1":
        try:
            from services.sentinela_auto import run_auto_workflows

            auto_started = run_auto_workflows(db, notify=notify)
        except Exception:
            pass

    return {
        "date": date_str,
        "message_chars": len(message),
        "radar": radar_result,
        "auto_workflows": auto_started,
    }
