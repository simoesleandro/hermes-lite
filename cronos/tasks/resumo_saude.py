import os
from datetime import datetime
from zoneinfo import ZoneInfo

from services.syshealth_client import SysHealthClient
from cronos.notifier import send_embed

_WEBHOOK = os.getenv("DISCORD_WEBHOOK_SAUDE", "")
_COLOR = 0x57F287
_META_AGUA = 3000
_META_PROTEINA = 150
_TZ = ZoneInfo("America/Sao_Paulo")


def run() -> None:
    client = SysHealthClient(os.getenv("SYSHEALTH_URL", "http://localhost:5060"))
    data = client.get_health_summary()
    hoje = datetime.now(_TZ).strftime("%d/%m/%Y")

    if data.get("offline"):
        send_embed(
            _WEBHOOK,
            title=f"📊 Resumo de Saúde — {hoje}",
            description="⚠️ SysHealth offline — dados indisponíveis.",
            color=0x99AAB5,
        )
        return

    agua = data.get("agua") or 0
    proteina = data.get("proteina") or 0

    obs = []
    if agua < 2000:
        obs.append("⚠️ Hidratação baixa")
    if proteina < 100:
        obs.append("⚠️ Proteína abaixo da meta")

    pct_agua = round(agua / _META_AGUA * 100)
    pct_prot = round(proteina / _META_PROTEINA * 100)

    def _v(val, unit=""):
        return f"{val}{unit}" if val is not None else "—"

    fields = [
        {"name": "💧 Água",       "value": f"{_v(agua, 'ml')} ({pct_agua}% de {_META_AGUA}ml)", "inline": True},
        {"name": "⚖️ Peso",       "value": _v(data.get("peso"), "kg"),                           "inline": True},
        {"name": "🥩 Proteína",   "value": f"{_v(proteina, 'g')} ({pct_prot}% de {_META_PROTEINA}g)", "inline": True},
        {"name": "😴 Sono",       "value": _v(data.get("sono"), "h"),                            "inline": True},
        {"name": "🚶 Passos",     "value": _v(data.get("passos")),                               "inline": True},
        {"name": "🏋️ Treino",    "value": _v(data.get("treino")),                               "inline": True},
        {"name": "💉 Tirzepatida","value": _v(data.get("tirzepatida")),                          "inline": True},
    ]

    desc = " · ".join(obs) if obs else "Dia dentro das metas ✅"
    send_embed(_WEBHOOK, title=f"📊 Resumo de Saúde — {hoje}", description=desc, color=_COLOR, fields=fields)
