"""Task Cronos — Radar GitHub diário."""

import os

from services.github_radar import run_github_radar
from db.database import Database


def run() -> None:
    if os.getenv("GITHUB_RADAR_ENABLED", "1") != "1":
        return
    db = Database()
    run_github_radar(db, notify=True)
