import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.morning_digest import build_morning_message


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "digest.db"))


def test_build_morning_message_gtd(db, monkeypatch):
    monkeypatch.setattr(
        "services.morning_digest._health_block",
        lambda: ["🎯 Saúde", "Água: 1500/3000 ml"],
    )
    monkeypatch.setattr(
        "services.morning_digest._sentinela_block",
        lambda: (["🔎 Sentinela", "2 alertas abertos"], {}, []),
    )
    monkeypatch.setattr(
        "services.morning_digest._radar_block",
        lambda _db, _d: ["📡 Radar GitHub", "Sem curadoria hoje"],
    )
    db.create_task("t1", "Revisar PR", status="today", priority="high")
    db.create_task("t2", "Inbox item", status="inbox")

    msg = build_morning_message(db)
    assert "Revisar PR" in msg
    assert "Inbox: 1 pendente" in msg
    assert "Sentinela" in msg


def test_run_morning_digest_skipped(monkeypatch, db):
    monkeypatch.setenv("MORNING_DIGEST_ENABLED", "0")
    from services.morning_digest import run_morning_digest

    result = run_morning_digest(notify=False, db=db)
    assert result.get("skipped")
