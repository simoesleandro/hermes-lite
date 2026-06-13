import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import classify_agent


def test_saude_bebi():
    assert classify_agent("bebi água hoje") == "saude"

def test_saude_hrv():
    assert classify_agent("meu HRV foi 55 hoje") == "saude"

def test_saude_peso():
    assert classify_agent("meu peso hoje foi 78kg") == "saude"

def test_treino_corrida():
    assert classify_agent("fiz uma corrida de 5km") == "treino"

def test_treino_ppl():
    assert classify_agent("treino PPL hoje foi peito") == "treino"

def test_desenvolvimento_bug():
    assert classify_agent("tem um bug no meu código python") == "desenvolvimento"

def test_desenvolvimento_refator():
    assert classify_agent("como refatorar essa função") == "desenvolvimento"

def test_sentinela_beats_juridico():
    assert classify_agent("anomalia no contrato público PNCP") == "sentinela"

def test_sentinela_licitacao():
    assert classify_agent("nova licitação no PNCP hoje") == "sentinela"

def test_juridico_lei():
    assert classify_agent("quero entender essa lei") == "juridico"

def test_juridico_clausula():
    assert classify_agent("analisar cláusula do contrato") == "juridico"

def test_juridico_processo_judicial():
    assert classify_agent("tenho um processo judicial em andamento") == "juridico"

def test_juridico_advogado():
    assert classify_agent("preciso de orientação de advogado") == "juridico"

def test_juridico_impugnar():
    assert classify_agent("como impugnar essa licitação") == "juridico"

def test_juridico_nao_captura_contrato_generico():
    # "contrato" sozinho não é jurídico — vai para analista ou sentinela
    assert classify_agent("liste os contratos do fornecedor X") == "analista"

def test_analista_fornecedor():
    assert classify_agent("quais os maiores fornecedores?") == "analista"

def test_analista_top5():
    assert classify_agent("top 5 contratos por valor") == "analista"

def test_analista_ranking():
    assert classify_agent("ranking de fornecedores por valor") == "analista"

def test_analista_maior_valor():
    assert classify_agent("contrato de maior valor em 2024") == "analista"

def test_analista_sentinela_db():
    assert classify_agent("consultar sentinela db por orgao") == "analista"

def test_analista_quais_os():
    assert classify_agent("quais os contratos acima de 1 milhão") == "analista"

def test_analista_liste_contratos():
    assert classify_agent("liste os contratos do mês passado") == "analista"

def test_investigador_pesquisar():
    assert classify_agent("pesquisar notícias sobre IA") == "investigador"

def test_leitor_pdf():
    assert classify_agent("resumir arquivo pdf do edital") == "leitor"

def test_analista_grafico():
    assert classify_agent("fazer um gráfico de vendas") == "analista"

def test_produtividade_tarefa():
    assert classify_agent("tenho uma tarefa importante hoje") == "produtividade"

def test_default_conhecimento():
    assert classify_agent("me explica o universo") == "conhecimento"

def test_default_empty():
    assert classify_agent("") == "conhecimento"

def test_ops_status():
    assert classify_agent("status dos serviços") == "ops"

def test_ops_cronos():
    assert classify_agent("reiniciar o cronos") == "ops"

def test_ops_hermes():
    assert classify_agent("hermes online?") == "ops"


def test_regex_multiple_matches():
    from app_factory import classify_agent_regex_matches
    matches = classify_agent_regex_matches("treino de código python com bug")
    assert "treino" in matches
    assert "desenvolvimento" in matches


def test_no_match_without_llm():
    assert classify_agent("me explica o universo", llm_fallback=False) == "conhecimento"


def test_ambiguous_uses_llm(monkeypatch):
    monkeypatch.setattr(
        "app_factory._classify_agent_llm",
        lambda msg, candidates=None: "desenvolvimento",
    )
    assert classify_agent(
        "treino de código python com bug",
        llm_fallback=True,
        llm_disambiguate=True,
    ) == "desenvolvimento"


def test_ambiguous_without_llm_returns_first():
    assert classify_agent("como impugnar essa licitação", llm_fallback=False) == "juridico"


def test_no_match_uses_llm(monkeypatch):
    monkeypatch.setattr(
        "app_factory._classify_agent_llm",
        lambda msg, candidates=None: "investigador",
    )
    assert classify_agent("me explica o universo", llm_fallback=True) == "investigador"
