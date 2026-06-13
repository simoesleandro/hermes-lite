import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.sentinela_auto import alert_key, run_auto_workflows


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "auto.db"))


def test_alert_key_uses_id():
    assert alert_key({"id": 42, "fornecedor": "X"}) == "id:42"


def test_alert_key_hash_stable():
    a = {"fornecedor": "ACME", "tipo": "fracionamento", "descricao": "teste"}
    assert alert_key(a) == alert_key(a)


def test_run_auto_workflows_dedup(db, monkeypatch):
    monkeypatch.setenv("SENTINELA_AUTO_WORKFLOW", "1")
    monkeypatch.setenv("SENTINELA_AUTO_MAX", "2")

    alerts = [
        {"id": 1, "fornecedor": "A", "severidade": "alta", "tipo": "t1"},
        {"id": 2, "fornecedor": "B", "severidade": "alta", "tipo": "t2"},
    ]

    class FakeClient:
        def get_resumo(self):
            return {"offline": False, "alertas_abertos": 2}

        def get_alertas(self, severidade=None, limit=10):
            return alerts

    started: list[str] = []

    def fake_start(db, *, alert=None, **kwargs):
        wf = f"wf-{alert['id']}"
        started.append(wf)
        return wf

    monkeypatch.setattr("services.sentinela_auto.SentinelaClient", FakeClient)
    monkeypatch.setattr("services.sentinela_auto.start_investigacao_parecer", fake_start)

    first = run_auto_workflows(db, notify=False)
    second = run_auto_workflows(db, notify=False)

    assert len(first) == 2
    assert second == []
    assert db.has_sentinela_auto_workflow("id:1")


def test_run_auto_workflows_disabled(db, monkeypatch):
    monkeypatch.setenv("SENTINELA_AUTO_WORKFLOW", "0")
    assert run_auto_workflows(db, notify=False) == []
