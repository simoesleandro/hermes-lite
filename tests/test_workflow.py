import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.workflow import strip_agent_prefix, write_parecer_export


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "wf.db"))


def test_strip_agent_prefix():
    assert strip_agent_prefix("🤖 Jurídico\n\nParecer aqui") == "Parecer aqui"
    assert strip_agent_prefix("texto direto") == "texto direto"


def test_write_parecer_export(tmp_path, monkeypatch):
    import services.workflow as wf
    monkeypatch.setattr(wf, "EXPORTS_DIR", tmp_path / "exports")
    path = write_parecer_export(
        "wf-123",
        "Dossiê teste",
        "Parecer teste",
        sources=[{"n": 1, "title": "Fonte A", "url": "https://example.com"}],
        meta={"fornecedor": "ACME"},
    )
    assert os.path.isfile(path)
    content = open(path, encoding="utf-8").read()
    assert "Dossiê teste" in content
    assert "Parecer teste" in content
    assert "ACME" in content


def test_workflow_crud(db):
    db.create_workflow("wf-1", "investigacao_parecer", {"context": "teste"})
    wf = db.get_workflow("wf-1")
    assert wf["status"] == "pending"
    assert wf["input_json"]["context"] == "teste"
    db.update_workflow("wf-1", status="running", output_json={"step": "investigador"})
    wf2 = db.get_workflow("wf-1")
    assert wf2["status"] == "running"
    assert wf2["output_json"]["step"] == "investigador"
    listed = db.list_workflows()
    assert len(listed) == 1
