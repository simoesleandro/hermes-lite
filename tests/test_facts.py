import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.facts import slug_key, try_handle_facts


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "facts.db"))


def test_slug_key():
    assert slug_key("Meta Peso 83kg") == "meta_peso_83kg"


def test_remember_and_list(db):
    r = try_handle_facts("lembrar que meta peso é 83 kg", db)
    assert r and "salvo" in r.lower()
    facts = db.list_facts()
    assert len(facts) == 1
    assert "83" in facts[0]["value"]


def test_remember_kv(db):
    r = try_handle_facts("lembrar fiap = agosto 2026 ADS", db)
    assert r and "fiap" in r.lower()
    assert db.find_fact("fiap")["value"] == "agosto 2026 ADS"


def test_list_facts_command(db):
    db.upsert_fact("meta_peso", "83kg")
    r = try_handle_facts("listar fatos", db)
    assert r and "meta_peso" in r


def test_forget_fact(db):
    db.upsert_fact("temp", "valor")
    r = try_handle_facts("esquecer fato temp", db)
    assert r and "removido" in r.lower()
    assert db.list_facts() == []


def test_format_facts_context(db):
    db.upsert_fact("meta", "83kg")
    ctx = db.format_facts_context()
    assert "FATOS SOBRE O USUÁRIO" in ctx
    assert "meta" in ctx


def test_pending_auto_fact_approve(db):
    db.upsert_fact("objetivo", "83kg", category="auto", status="pending")
    pending = db.list_facts(status="pending")
    assert len(pending) == 1
    assert db.approve_fact("objetivo")
    assert db.list_facts(status="pending") == []
    confirmed = db.find_fact("objetivo")
    assert confirmed and confirmed.get("status") == "confirmed"


def test_confirmed_not_overwritten_by_auto(db):
    db.upsert_fact("meta", "83kg", status="confirmed")
    db.upsert_fact("meta", "84kg", category="auto", status="pending")
    assert db.find_fact("meta")["value"] == "84kg"
    assert db.find_fact("meta")["status"] == "confirmed"
