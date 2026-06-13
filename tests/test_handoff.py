import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.handoff import build_juridico_handoff_message, is_juridico_handoff


def test_build_handoff_message():
    msg = build_juridico_handoff_message("Contrato X com irregularidade.", [
        {"n": 1, "title": "PNCP Contrato", "url": "https://pncp.gov.br/1"},
    ])
    assert "=== DOSSIÊ INVESTIGATIVO ===" in msg
    assert "Contrato X" in msg
    assert "PNCP Contrato" in msg
    assert is_juridico_handoff(msg)


def test_build_handoff_without_sources():
    msg = build_juridico_handoff_message("Relatório simples")
    assert "=== FONTES ===" not in msg
    assert "Relatório simples" in msg


def test_is_juridico_handoff():
    assert is_juridico_handoff("texto\n=== DOSSIÊ INVESTIGATIVO ===\nfoo")
    assert not is_juridico_handoff("pergunta normal sobre lei")


def test_build_investigador_handoff_from_alert():
    from services.handoff import build_investigador_handoff_message, is_sentinela_handoff
    msg = build_investigador_handoff_message("", alert={
        "fornecedor": "ACME Ltda",
        "tipo": "Dispensa irregular",
        "severidade": "alta",
    })
    assert "=== CONTEXTO SENTINELA ===" in msg
    assert "ACME Ltda" in msg
    assert is_sentinela_handoff(msg)


def test_build_investigador_handoff_from_context():
    from services.handoff import build_investigador_handoff_message
    msg = build_investigador_handoff_message("Contrato 123 acima do limiar")
    assert "Contrato 123" in msg
