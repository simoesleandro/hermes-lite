import os
from datetime import datetime
from zoneinfo import ZoneInfo

from services.syshealth_client import SysHealthClient
from services.sentinela_client import SentinelaClient
from cronos.notifier import send_embed

_WEBHOOK = os.getenv("DISCORD_WEBHOOK_BRIEFING", "")
_COLOR = 0x5865F2
_TZ = ZoneInfo("America/Sao_Paulo")
_DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def run() -> None:
    agora = datetime.now(_TZ)
    data_fmt = agora.strftime("%d/%m/%Y")
    dia_semana = _DIAS_PT[agora.weekday()]
    hora_fmt = agora.strftime("%H:%M")

    treinos = SysHealthClient(os.getenv("SYSHEALTH_URL", "http://localhost:5060")).get_treinos_recentes(dias=1)
    if treinos:
        agenda = treinos[0].get("descricao") or treinos[0].get("tipo") or "Treino registrado"
    else:
        agenda = "Dia de descanso"

    resumo = SentinelaClient().get_resumo()
    alertas_txt = "Sentinela offline" if resumo.get("offline") else f"{resumo.get('alertas_abertos', 0)} alertas abertos"

    fields = [
        {"name": "📅 Agenda do dia",  "value": agenda,                              "inline": False},
        {"name": "🎯 Metas de hoje",  "value": "Água: 3000ml  |  Proteína: 150g",   "inline": False},
        {"name": "🔎 Sentinela",      "value": alertas_txt,                         "inline": False},
    ]

    send_embed(
        _WEBHOOK,
        title=f"☀️ Bom dia, Leandro! — {data_fmt} · {dia_semana}",
        description="",
        color=_COLOR,
        fields=fields,
        footer=f"Hermes Cronos • {hora_fmt}",
    )
