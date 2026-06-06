import os
from datetime import datetime
from zoneinfo import ZoneInfo

from services.syshealth_client import SysHealthClient
from cronos.notifier import send_telegram

_META_AGUA = 3000
_META_PROTEINA = 150
_TZ = ZoneInfo("America/Sao_Paulo")


def run() -> None:
    client = SysHealthClient(os.getenv("SYSHEALTH_URL", "http://localhost:5060"))
    data = client.get_health_summary()
    hoje = datetime.now(_TZ).strftime("%d/%m/%Y")

    if data.get("offline"):
        send_telegram(f"📊 Resumo de Saúde — {hoje}\n⚠️ SysHealth offline — dados indisponíveis.")
        return

    agua = data.get("agua_hoje_ml") or 0
    proteina = data.get("proteina_g") or 0

    obs = []
    if agua < 2000:
        obs.append("⚠️ Hidratação baixa")
    if proteina < 100:
        obs.append("⚠️ Proteína abaixo da meta")

    pct_agua = round(agua / _META_AGUA * 100)
    pct_prot = round(proteina / _META_PROTEINA * 100)

    def _v(val, unit=""):
        return f"{val}{unit}" if val is not None else "—"

    desc = " · ".join(obs) if obs else "Dia dentro das metas ✅"

    msg = (
        f"📊 Resumo de Saúde — {hoje}\n{desc}\n\n"
        f"💧 Água: {_v(agua, 'ml')} ({pct_agua}% de {_META_AGUA}ml)\n"
        f"⚖️ Peso: {_v(data.get('peso_kg'), 'kg')}\n"
        f"🥩 Proteína: {_v(proteina, 'g')} ({pct_prot}% de {_META_PROTEINA}g)\n"
        f"😴 Sono: {_v(data.get('sono_horas'), 'h')}\n"
        f"🚶 Passos: {_v(data.get('passos_hoje'))}\n"
        f"🏋️ Treino: {_v(data.get('treino_hoje'))}\n"
        f"💉 Tirzepatida: {_v(data.get('tirzepatida_hoje'))}"
    )
    send_telegram(msg)
