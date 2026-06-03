import logging
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger("cronos.scheduler")

_TZ = ZoneInfo("America/Sao_Paulo")


def should_run(task_config: dict, last_run: date | None) -> bool:
    agora = datetime.now(_TZ)
    if last_run == agora.date():
        return False
    if task_config["weekday"] is not None:
        if agora.weekday() != task_config["weekday"]:
            return False
    return agora.hour == task_config["hour"] and agora.minute == task_config["minute"]


def run_loop(tasks_registry: list[dict]) -> None:
    """
    Cada entrada em tasks_registry:
    {
        "name": str,
        "fn": callable,           # já envolvido com tratamento de erro
        "schedule": {"hour": int, "minute": int, "weekday": int | None},
        "last_run": date | None,
    }
    """
    logger.info("Scheduler iniciado — checando a cada 30s.")
    while True:
        for task in tasks_registry:
            if should_run(task["schedule"], task["last_run"]):
                logger.info("Executando tarefa: %s", task["name"])
                task["fn"]()
                task["last_run"] = datetime.now(_TZ).date()
        time.sleep(30)
