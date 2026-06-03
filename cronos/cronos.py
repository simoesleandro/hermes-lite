import logging
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

from cronos.notifier import send_embed
from cronos.scheduler import run_loop
from cronos.tasks import briefing, resumo_saude, sentinela_semanal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cronos")

import os
_WEBHOOK_LOGS = os.getenv("DISCORD_WEBHOOK_LOGS", "")
_TZ = ZoneInfo("America/Sao_Paulo")


def _log(msg: str) -> None:
    send_embed(_WEBHOOK_LOGS, title="Hermes Cronos", description=msg, color=0x99AAB5)


def _wrap(name: str, fn):
    def wrapped():
        try:
            fn()
        except Exception:
            tb = traceback.format_exc()[:500]
            logger.error("Erro em %s:\n%s", name, tb)
            _log(f"❌ Erro em `{name}`:\n```\n{tb}\n```")
    return wrapped


_TASKS = [
    {
        "name": "briefing",
        "fn": _wrap("briefing", briefing.run),
        "schedule": {"hour": 9, "minute": 30, "weekday": None},
        "last_run": None,
    },
    {
        "name": "resumo_saude",
        "fn": _wrap("resumo_saude", resumo_saude.run),
        "schedule": {"hour": 22, "minute": 0, "weekday": None},
        "last_run": None,
    },
    {
        "name": "sentinela_semanal",
        "fn": _wrap("sentinela_semanal", sentinela_semanal.run),
        "schedule": {"hour": 9, "minute": 30, "weekday": 0},
        "last_run": None,
    },
]


def main() -> None:
    now = datetime.now(_TZ).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Cronos iniciando...")
    _log(f"🟢 Cronos online — {now}")
    run_loop(_TASKS)


if __name__ == "__main__":
    main()
