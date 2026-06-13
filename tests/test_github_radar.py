import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.github_radar import curate_with_llm, render_digest_markdown


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "radar.db"))


def test_render_digest_markdown():
    picks = [{
        "full_name": "org/tool",
        "nota": 8.5,
        "o_que_faz": "Faz X",
        "como_usar": "pip install x",
        "raciocinio": "Útil para MCP",
        "html_url": "https://github.com/org/tool",
        "stars": 1200,
        "language": "Python",
        "tags": ["mcp"],
    }]
    md = render_digest_markdown(picks, "2026-06-13")
    assert "8.5/10" in md
    assert "org/tool" in md
    assert "Como usar" in md


def test_curate_with_mock_llm(db, monkeypatch):
    monkeypatch.setattr(
        "services.github_radar.fetch_readme_excerpt",
        lambda name, **kw: "# readme",
    )
    candidates = [{
        "full_name": "acme/lib",
        "html_url": "https://github.com/acme/lib",
        "description": "lib",
        "stars": 500,
        "language": "Python",
        "topics": ["mcp"],
    }]

    def fake_llm(messages, complexity):
        return json.dumps({
            "picks": [{
                "full_name": "acme/lib",
                "nota": 9,
                "o_que_faz": "Biblioteca MCP",
                "como_usar": "pip install acme-lib",
                "raciocinio": "Combina com Hermes",
                "tags": ["mcp"],
            }],
        })

    import model_router
    monkeypatch.setattr(model_router, "get_completion", fake_llm)
    picks = curate_with_llm(candidates, db)
    assert len(picks) == 1
    assert picks[0]["nota"] == 9.0


def test_github_digest_db(db):
    db.save_github_digest("id1", "2026-06-13", "# md", [{"full_name": "a/b"}], "/tmp/x.md")
    d = db.get_github_digest_by_date("2026-06-13")
    assert d["picks"][0]["full_name"] == "a/b"
    db.mark_github_seen("a/b", score=9.0)
    assert db.list_github_seen()[0]["full_name"] == "a/b"
