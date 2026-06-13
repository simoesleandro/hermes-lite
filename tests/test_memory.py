import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.base import BaseAgent
from db.database import Database
from model_router import Complexity


class _StubAgent(BaseAgent):
    name = "conhecimento"
    complexity = Complexity.SIMPLE
    system_prompt = "Stub."


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "mem.db"))


def test_memory_block_includes_other_conversations(db, monkeypatch):
    monkeypatch.setenv("CROSS_CHAT_MEMORY", "1")
    agent = _StubAgent(db)
    db.create_conversation("c1", "T1", "conhecimento")
    db.create_conversation("c2", "T2", "conhecimento")
    db.save_message("conhecimento", "user", "Gosto de astronomia", "s1", conversation_id="c1")

    block = agent._memory_block("c2")
    assert "astronomia" in block


def test_memory_block_disabled(db, monkeypatch):
    monkeypatch.setenv("CROSS_CHAT_MEMORY", "0")
    agent = _StubAgent(db)
    db.create_conversation("c1", "T1", "conhecimento")
    db.save_message("conhecimento", "user", "Fato X", "s1", conversation_id="c1")

    assert agent._memory_block("c2") == ""


def test_get_history_uses_conversation_id(db):
    agent = _StubAgent(db)
    db.create_conversation("c1", "T", "conhecimento")
    db.create_conversation("c2", "T2", "conhecimento")
    db.save_message("conhecimento", "user", "Msg conv1", "sess-a", conversation_id="c1")
    db.save_message("conhecimento", "user", "Msg sess", "sess-b")

    hist = agent._get_history("sess-b", "c1")
    assert len(hist) == 1
    assert hist[0]["content"] == "Msg conv1"
