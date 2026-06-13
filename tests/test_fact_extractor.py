import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.fact_extractor import auto_extract_enabled, extract_facts_from_message


def test_auto_extract_disabled_by_default():
    assert not auto_extract_enabled()


def test_extract_skips_short_message(monkeypatch):
    monkeypatch.setenv("USER_FACTS_AUTO", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert extract_facts_from_message("oi") == []


def test_extract_with_mock_llm(monkeypatch):
    monkeypatch.setenv("USER_FACTS_AUTO", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    def fake_completion(messages, complexity):
        return '[{"key": "meta_peso", "value": "83 kg"}]'

    import model_router
    monkeypatch.setattr(model_router, "get_completion", fake_completion)

    facts = extract_facts_from_message("Minha meta de peso é 83 kg até dezembro")
    assert len(facts) == 1
    assert facts[0]["value"] == "83 kg"
