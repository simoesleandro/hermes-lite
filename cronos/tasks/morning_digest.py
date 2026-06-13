"""Task Cronos — digest matinal unificado."""

from services.morning_digest import run_morning_digest


def run() -> None:
    run_morning_digest(notify=True)
