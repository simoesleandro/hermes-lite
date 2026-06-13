import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.agent_hub import AgentHub


def test_desenvolvimento_injects_git_context(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "services.git_tools.format_git_context",
        lambda **kw: "=== GIT (hermes-lite) ===\nbranch: master",
    )
    from agents.desenvolvimento import DesenvolvimentoAgent

    agent = DesenvolvimentoAgent(db=Database(path=str(tmp_path / "dev.db")))
    msgs = agent._build_messages("mostre o git diff", "s1")
    system = msgs[0]["content"]
    assert "GIT" in system
