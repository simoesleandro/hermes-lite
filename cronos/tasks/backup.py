"""Task Cronos — backup noturno hermes.db + exports."""

from services.backup import run_backup


def run() -> None:
    run_backup()
