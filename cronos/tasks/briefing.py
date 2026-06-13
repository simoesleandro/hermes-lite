import os
from datetime import datetime
from zoneinfo import ZoneInfo

from services.syshealth_client import SysHealthClient
from services.sentinela_client import SentinelaClient
from cronos.notifier import notify

_TZ = ZoneInfo("America/Sao_Paulo")
_DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def run() -> None:
    agora = datetime.now(_TZ)
    data_fmt = agora.strftime("%d/%m/%Y")
    dia_semana = _DIAS_PT[agora.weekday()]
    hora_fmt = agora.strftime("%H:%M")

    sh = SysHealthClient(os.getenv("SYSHEALTH_URL", "http://localhost:5060"))
    treinos = sh.get_treinos_recentes(dias=1)
    if treinos:
        agenda = treinos[0].get("descricao") or treinos[0].get("tipo") or "Treino registrado"
    else:
        agenda = "Dia de descanso"

    summary = sh.get_health_summary()
    if summary.get("offline"):
        metas_txt = "SysHealth offline"
    else:
        agua = summary.get("agua_hoje_ml") or 0
        prot = summary.get("proteina_g")
        prot_txt = f"{prot}g" if prot is not None else "—"
        falta_agua = max(0, 3000 - agua)
        metas_txt = f"Água: {agua}/3000 ml (faltam {falta_agua})  |  Proteína: {prot_txt}/190g"

    resumo = SentinelaClient().get_resumo()
    alertas_txt = "Sentinela offline" if resumo.get("offline") else f"{resumo.get('alertas_abertos', 0)} alertas abertos"

    msg = (
        f"☀️ Bom dia, Leandro! — {data_fmt} · {dia_semana}\n\n"
        f"📅 Agenda do dia\n{agenda}\n\n"
        f"🎯 Metas de hoje\n{metas_txt}\n\n"
        f"🔎 Sentinela\n{alertas_txt}\n\n"
        f"Hermes Cronos • {hora_fmt}"
    )
    notify(msg, title="Briefing diário", discord_webhook=os.getenv("DISCORD_WEBHOOK_BRIEFING"))

    if not resumo.get("offline") and resumo.get("alertas_abertos", 0) > 0:
        try:
            from services.sentinela_telegram import send_alerts_panel
            send_alerts_panel()
        except Exception:
            pass
