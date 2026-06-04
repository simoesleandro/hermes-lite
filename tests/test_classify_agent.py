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

def test_juridico_contrato():
    assert classify_agent("revisar meu contrato de trabalho") == "juridico"

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
