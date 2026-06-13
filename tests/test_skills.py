"""Tests for agent skills and source extraction."""

from agents.skills import apply_skill, extract_sources, list_skills


def test_list_skills_all():
    skills = list_skills()
    assert "investigador" in skills
    assert "dossie" in skills["investigador"]


def test_list_skills_single_agent():
    skills = list_skills("saude")
    assert "saude" in skills
    assert "conhecimento" not in skills


def test_apply_skill_prepends_prompt():
    out = apply_skill("investigador", "rapido", "Quem ganhou a licitação?")
    assert "Modo rápido" in out
    assert "Quem ganhou" in out


def test_apply_skill_unknown_returns_message():
    msg = "hello"
    assert apply_skill("conhecimento", "nope", msg) == msg


def test_extract_sources_web_and_contratos():
    resultados = {
        "buscar_web": [{"title": "Notícia X", "href": "https://example.com/a"}],
        "buscar_contratos": [
            {"fornecedor": "ACME", "numero_controle_pncp": "12345", "objeto": "Serviços"},
        ],
    }
    sources = extract_sources(resultados)
    assert len(sources) == 2
    assert sources[0]["n"] == 1
    assert sources[0]["url"] == "https://example.com/a"
    assert "pncp.gov.br" in sources[1]["url"]
