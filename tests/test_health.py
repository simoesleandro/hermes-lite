import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.health import get_health


def test_get_health_structure():
    h = get_health(include_providers=False)
    assert "ok" in h
    assert h["hermes"]["database"]["status"] == "online"
    assert h["hermes"]["agents"] == 11
    assert "telegram" in h
    assert h["telegram"]["bot_enabled"] is True


def test_get_health_with_providers(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    h = get_health(include_providers=True)
    assert "providers" in h
    assert h["providers"]["groq"]["status"] == "offline"
