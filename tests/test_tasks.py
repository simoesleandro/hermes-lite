import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.produtividade import ProdutividadeAgent
from db.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "tasks.db"))


@pytest.fixture
def agent(db):
    return ProdutividadeAgent(db)


def test_create_and_list_tasks(db):
    db.create_task("t1", "Revisar PR", status="today", priority="high")
    db.create_task("t2", "Ligar pro banco", status="inbox")
    tasks = db.list_tasks(status="today")
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Revisar PR"


def test_complete_task(db):
    db.create_task("t1", "Enviar relatório", status="week")
    assert db.complete_task("t1")
    assert db.list_tasks(status="week") == []


def test_find_open_task(db):
    db.create_task("t1", "Estudar Python async", status="inbox")
    found = db.find_open_task("python async")
    assert found is not None
    assert found["id"] == "t1"


def test_format_tasks_context(db):
    db.create_task("t1", "Tarefa hoje", status="today")
    ctx = db.format_tasks_context()
    assert "HOJE" in ctx
    assert "Tarefa hoje" in ctx


def test_agent_add_task_via_chat(agent):
    msgs = agent._build_messages("adicionar tarefa: revisar hermes-lite", "sess-1")
    system = msgs[0]["content"]
    assert "revisar hermes-lite" in system
    assert "Tarefa adicionada" in system or "revisar hermes-lite" in system


def test_agent_complete_task(agent):
    agent.db.create_task(str(uuid.uuid4()), "Comprar leite", status="today")
    msgs = agent._build_messages("concluir comprar leite", "sess-1")
    assert "concluída" in msgs[0]["content"].lower()


def test_tasks_summary(db):
    db.create_task("a", "A", status="today")
    db.create_task("b", "B", status="today")
    db.create_task("c", "C", status="inbox")
    s = db.tasks_summary()
    assert s["today"] == 2
    assert s["inbox"] == 1
    assert s["total_open"] == 3
