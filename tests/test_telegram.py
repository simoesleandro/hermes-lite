import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.agent_hub import AgentHub
from services.telegram_bot import handle_command
from services.telegram_client import split_message


@pytest.fixture
def hub(tmp_path):
    return AgentHub(db=Database(path=str(tmp_path / "tg.db")))


def test_split_long_message():
    text = "x" * 9000
    parts = split_message(text, limit=4096)
    assert len(parts) == 3
    assert sum(len(p) for p in parts) >= 9000 - 2


def test_handle_command_agente(hub):
    sid = "telegram-1"
    r = handle_command(hub, sid, "/agente sentinela")
    assert r is not None
    assert "Sentinela" in r
    assert hub.get_locked_agent(sid) == "sentinela"


def test_handle_command_auto(hub):
    sid = "telegram-2"
    handle_command(hub, sid, "/agente ops")
    r = handle_command(hub, sid, "/auto")
    assert hub.get_locked_agent(sid) is None
    assert "automático" in r.lower()


def test_allowed_chat_ids_from_env(monkeypatch):
    from services import telegram_client
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111,222")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram_client.is_chat_allowed(111)
    assert not telegram_client.is_chat_allowed(333)
