import os
from datetime import datetime
from zoneinfo import ZoneInfo

from services.sentinela_client import SentinelaClient
from cronos.notifier import send_telegram

_TZ = ZoneInfo("America/Sao_Paulo")


def _brl(v) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def run() -> None:
    client = SentinelaClient()
    hoje = datetime.now(_TZ).strftime("%d/%m/%Y")

    resumo = client.get_resumo()
    alertas = client.get_alertas(severidade="alta", limit=5)
    top = client.top_contratos(limit=3)

    if resumo.get("offline"):
        send_telegram(
            f"🔎 Relatório Semanal Sentinela RJ — {hoje}\n"
            "⚠️ Sentinela offline — banco de dados indisponível."
        )
        return

    visao = (
        f"Contratos: {resumo['contratos']}\n"
        f"Valor total: {_brl(resumo['valor_total'])}\n"
        f"Alertas abertos: {resumo['alertas_abertos']}"
    )

    alertas_txt = "\n".join(
        f"• {a.get('fornecedor') or 'N/D'} — {a['tipo']} ({_brl(a.get('valor'))})"
        for a in alertas
    ) or "Nenhum alerta de alta severidade."

    top_txt = "\n".join(
        f"• {t.get('fornecedor') or 'N/D'} — {_brl(t.get('valor'))}"
        for t in top
    ) or "Sem dados."

    msg = (
        f"🔎 Relatório Semanal Sentinela RJ — {hoje}\n"
        f"Última coleta: {resumo.get('ultima_coleta') or 'desconhecida'}\n\n"
        f"📊 Visão Geral\n{visao}\n\n"
        f"🚨 Top Alertas Alta Severidade\n{alertas_txt}\n\n"
        f"💰 Maiores Contratos\n{top_txt}"
    )
    send_telegram(msg)
