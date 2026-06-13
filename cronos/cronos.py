import logging
import os
import sys
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from cronos.notifier import notify
from cronos.scheduler import run_loop
from cronos.tasks import morning_digest, resumo_saude, sentinela_semanal, backup, facts_review

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cronos")

_TZ = ZoneInfo("America/Sao_Paulo")


def _log(msg: str) -> None:
    notify(f"Hermes Cronos\n{msg}", title="Cronos")


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
        "name": "morning_digest",
        "fn": _wrap("morning_digest", morning_digest.run),
        "schedule": {"hour": 7, "minute": 30, "weekday": None},
        "last_run": None,
    },
    {
        "name": "backup",
        "fn": _wrap("backup", backup.run),
        "schedule": {"hour": 3, "minute": 0, "weekday": None},
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
    {
        "name": "facts_review",
        "fn": _wrap("facts_review", facts_review.run),
        "schedule": {"hour": 10, "minute": 0, "weekday": 6},
        "last_run": None,
    },
]


def main() -> None:
    if "--test" in sys.argv:
        logger.info("Modo teste — disparando todas as tasks...")
        from cronos.tasks.resumo_saude import run as run_saude
        from cronos.tasks.morning_digest import run as run_digest
        from cronos.tasks.sentinela_semanal import run as run_sentinela
        from cronos.tasks.backup import run as run_backup
        from cronos.tasks.facts_review import run as run_facts_review
        run_backup()
        run_digest()
        run_saude()
        run_sentinela()
        run_facts_review()
        logger.info("Modo teste concluído.")
        sys.exit(0)

    now = datetime.now(_TZ).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Cronos iniciando...")
    _log(f"🟢 Cronos online — {now}")
    run_loop(_TASKS)


if __name__ == "__main__":
    main()
