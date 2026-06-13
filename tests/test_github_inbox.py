import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.github_inbox import build_inbox_lines, fetch_github_inbox


def test_fetch_github_inbox_disabled(monkeypatch):
    monkeypatch.setenv("GITHUB_INBOX_ENABLED", "0")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    data = fetch_github_inbox()
    assert data.get("offline") is True


def test_build_inbox_lines_full(monkeypatch):
    monkeypatch.setenv("GITHUB_INBOX_ENABLED", "1")
    data = {
        "enabled": True,
        "offline": False,
        "user": "dev",
        "prs_open": [{"repo": "dev/app", "number": 1, "title": "Feature X"}],
        "prs_review": [{"repo": "org/lib", "number": 9, "title": "Fix bug"}],
        "issues_assigned": [],
        "ci_failures": [{"repo": "dev/app", "name": "pytest"}],
    }
    lines = build_inbox_lines(data)
    text = "\n".join(lines)
    assert "PRs abertos" in text
    assert "dev/app#1" in text
    assert "Reviews pendentes" in text
    assert "CI falhou" in text


def test_build_inbox_offline():
    lines = build_inbox_lines({"enabled": True, "offline": True, "reason": "sem token"})
    assert "sem token" in "\n".join(lines)
