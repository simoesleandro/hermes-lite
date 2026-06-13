import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.dashboard import get_dashboard


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "dash.db"))


def test_dashboard_gtd(db):
    db.create_task("t1", "Deploy", status="today", priority="high")
    data = get_dashboard(db)
    assert data["gtd"]["summary"]["today"] == 1
    assert data["gtd"]["today"][0]["title"] == "Deploy"


def test_dashboard_offline_sentinela(db, monkeypatch):
    class Offline:
        def get_resumo(self):
            return {"offline": True}

        def get_alertas(self, **kwargs):
            return []

        def get_estatisticas(self):
            return {"offline": True}

    monkeypatch.setattr("services.dashboard.SentinelaClient", Offline)
    monkeypatch.setattr(
        "services.dashboard.fetch_github_inbox",
        lambda: {"enabled": False, "offline": True},
    )
    monkeypatch.setattr(
        "services.dashboard.SysHealthClient",
        lambda url: type("SH", (), {"get_health_summary": lambda self: {"offline": True}})(),
    )
    data = get_dashboard(db)
    assert data["sentinela"]["resumo"]["offline"] is True
