import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "test.db"))


def test_create_conversation(db):
    db.create_conversation("abc-123", "Bebi água hoje", "saude")
    convs = db.get_conversations()
    assert len(convs) == 1
    assert convs[0]["id"] == "abc-123"
    assert convs[0]["agent"] == "saude"
    assert convs[0]["title"] == "Bebi água hoje"


def test_get_conversation_messages(db):
    db.create_conversation("conv-1", "Teste", "conhecimento")
    db.save_message("conhecimento", "user",      "Olá", "sess-1", conversation_id="conv-1")
    db.save_message("conhecimento", "assistant", "Oi!", "sess-1", conversation_id="conv-1")
    msgs = db.get_conversation_messages("conv-1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Olá"
    assert msgs[1]["role"] == "assistant"


def test_save_message_backwards_compat(db):
    db.save_message("conhecimento", "user", "Teste", "sess-old")
    history = db.get_history_as_messages("conhecimento", "sess-old")
    assert len(history) == 1
    assert history[0]["content"] == "Teste"


def test_duplicate_conversation_ignored(db):
    db.create_conversation("dup-1", "Título Original", "treino")
    db.create_conversation("dup-1", "Outro Título",    "treino")
    convs = db.get_conversations()
    assert len(convs) == 1
    assert convs[0]["title"] == "Título Original"


def test_get_conversations_empty(db):
    assert db.get_conversations() == []


def test_get_conversation_messages_empty(db):
    assert db.get_conversation_messages("nonexistent") == []


def test_search_conversations(db):
    db.create_conversation("conv-search", "Contrato PNCP suspeito", "sentinela")
    db.save_message("sentinela", "user", "anomalia no contrato público", "s1", conversation_id="conv-search")
    db.save_message("sentinela", "assistant", "Alerta de superfaturamento detectado", "s1", conversation_id="conv-search")
    results = db.search_conversations("superfaturamento")
    assert len(results) >= 1
    assert results[0]["id"] == "conv-search"


def test_export_conversation_markdown(db):
    db.create_conversation("conv-exp", "Parecer jurídico", "juridico")
    db.save_message("juridico", "user", "Analise a dispensa", "s1", conversation_id="conv-exp")
    db.save_message("juridico", "assistant", "Art. 75 inciso II aplicável", "s1", conversation_id="conv-exp")
    md = db.export_conversation_markdown("conv-exp")
    assert "# Parecer jurídico" in md
    assert "juridico" in md
    assert "Art. 75" in md


def test_update_conversation_title(db):
    db.create_conversation("conv-upd", "Título antigo", "saude")
    assert db.update_conversation("conv-upd", "Título novo") is True
    meta = db.get_conversation("conv-upd")
    assert meta["title"] == "Título novo"


def test_update_conversation_missing(db):
    assert db.update_conversation("missing", "X") is False


def test_delete_conversation(db):
    db.create_conversation("conv-del", "Apagar", "ops")
    db.save_message("ops", "user", "status", "s1", conversation_id="conv-del")
    assert db.delete_conversation("conv-del") is True
    assert db.get_conversation("conv-del") is None
    assert db.get_conversation_messages("conv-del") == []


def test_delete_conversation_missing(db):
    assert db.delete_conversation("missing") is False
