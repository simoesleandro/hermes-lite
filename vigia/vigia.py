import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

from cronos.notifier import send_embed
from vigia.monitor import SERVICES, check_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("vigia")

_WEBHOOK = os.getenv("DISCORD_WEBHOOK_LOGS", "")
_TZ = ZoneInfo("America/Sao_Paulo")

_COLOR_RED   = 0xED4245
_COLOR_GREEN = 0x57F287
_COLOR_GRAY  = 0x99AAB5

_SLEEP_SECONDS  = 300   # 5 min
_HEARTBEAT_ITER = 12    # a cada 12 iterações = 1 hora


def _hora() -> str:
    return datetime.now(_TZ).strftime("%H:%M")


def _alert_down(key: str) -> None:
    cfg = SERVICES[key]
    send_embed(
        _WEBHOOK,
        title=f"🔴 {cfg['emoji']} {cfg['name']} — OFFLINE",
        description=f"Serviço caiu às {_hora()}",
        color=_COLOR_RED,
    )


def _alert_up(key: str) -> None:
    cfg = SERVICES[key]
    send_embed(
        _WEBHOOK,
        title=f"🟢 {cfg['emoji']} {cfg['name']} — ONLINE",
        description=f"Serviço restaurado às {_hora()}",
        color=_COLOR_GREEN,
    )


def _heartbeat(status: dict) -> None:
    online = sum(1 for v in status.values() if v)
    total  = len(status)
    send_embed(
        _WEBHOOK,
        title="💓 Vigia online",
        description=f"{online}/{total} serviços operacionais",
        color=_COLOR_GRAY,
    )


def main() -> None:
    logger.info("Hermes Vigia iniciando...")
    send_embed(
        _WEBHOOK,
        title="👁️ Hermes Vigia iniciado",
        description=f"Monitorando {len(SERVICES)} serviços",
        color=_COLOR_GRAY,
    )

    _status_anterior: dict = {}
    _alertas_enviados: set = set()
    iteration = 0

    while True:
        status = check_all()
        logger.info("Status: %s", status)

        for key, online in status.items():
            anterior = _status_anterior.get(key)

            if anterior is True and not online and key not in _alertas_enviados:
                logger.warning("%s CAIU", key)
                _alert_down(key)
                _alertas_enviados.add(key)

            elif anterior is False and online and key in _alertas_enviados:
                logger.info("%s VOLTOU", key)
                _alert_up(key)
                _alertas_enviados.discard(key)

        _status_anterior = status
        iteration += 1

        if iteration % _HEARTBEAT_ITER == 0:
            _heartbeat(status)

        time.sleep(_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
