import re
from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from services.analista_sandbox import execute_code
from db.database import Database


_GENERATE_SYSTEM = """Você é um analista de dados especialista em Python.
Gere código Python para responder a pergunta do usuário.

Bases de dados disponíveis (variáveis já definidas no ambiente):
- SENTINELA_DB: SQLite com contratos públicos do Rio de Janeiro
  Tabelas:
    fornecedores(ni, tipo_pessoa, razao_social, primeira_vez, atualizado_em)
    contratos(numero_controle_pncp, orgao_cnpj, fornecedor_ni, objeto,
              valor_inicial, valor_global, data_assinatura,
              categoria_processo_nome, data_vigencia_inicio, data_vigencia_fim)
    alertas(id, contrato_id, tipo, descricao, severidade)
    orgaos(cnpj, razao_social, poder_id, esfera_id, municipio_nome,
           municipio_ibge, uf_sigla, primeira_vez, atualizado_em)
  JOINs corretos:
    contratos.fornecedor_ni = fornecedores.ni
    contratos.orgao_cnpj    = orgaos.cnpj
  Exemplos corretos:
    SELECT f.razao_social, SUM(c.valor_global) AS total
    FROM contratos c
    JOIN fornecedores f ON c.fornecedor_ni = f.ni
    GROUP BY f.razao_social ORDER BY total DESC LIMIT 10;

    SELECT * FROM alertas
    WHERE severidade = 'alta' ORDER BY id DESC;

- SYSHEALTH_DB: SQLite com dados de saúde pessoal
  Tabelas: refeicoes(calorias, proteinas, carboidratos, gorduras, data_hora),
  agua(quantidade_ml, data_hora), medidas(peso, data),
  amazfit_dados(passos, sono_total_min, hrv_ms, data_hora),
  hevy_treinos(titulo, duracao_min, volume_kg, data_hora)

Libs disponíveis: pandas, numpy, matplotlib, seaborn, sqlite3,
json, datetime, math, statistics, collections, itertools, re, csv

GRÁFICOS — OBRIGATÓRIO:
SEMPRE gere um gráfico matplotlib ao final de qualquer análise
com dados numéricos. Nunca retorne só texto quando há dados
para visualizar. O ambiente captura figuras abertas automaticamente
via plt.get_fignums() — NÃO chame save_chart() nem imprima base64.
Padrão obrigatório de estilo escuro:
  plt.style.use('dark_background')
  fig, ax = plt.subplots(figsize=(10, 5))
  fig.patch.set_facecolor('#0d1117')
  ax.set_facecolor('#0d1117')
  # ... plot ...
  plt.tight_layout()

Para dados tabulares: use print() com formatação clara.
Imprima os dados E gere o gráfico — ambos são capturados.

IMPORTANTE:
- Gere APENAS o código Python, sem explicações
- Sem markdown, sem ```python, só o código puro
- Use sqlite3.connect(SENTINELA_DB) ou sqlite3.connect(SYSHEALTH_DB)
- Para datas: datetime.datetime.now(), datetime.datetime.strptime()
- Código deve ser autocontido e executável"""


_INTERPRET_SYSTEM = """Você é um analista de dados.
O código Python foi executado. Interprete os resultados de forma clara e profissional.
Destaque insights importantes e padrões relevantes.
Se houver gráfico, descreva brevemente o que ele mostra.
Se houver erro, explique o que pode ter causado e sugira correção.
Responda em português."""


def _strip_fences(code: str) -> str:
    code = code.strip()
    code = re.sub(r"^```(?:python)?\s*\n?", "", code)
    code = re.sub(r"\n?```\s*$", "", code)
    return code.strip()


class AnalistaAgent(BaseAgent):
    name = "analista"
    complexity = Complexity.HEAVY

    def __init__(self, db: Database):
        super().__init__(db)

    def _generate_code(self, message: str) -> str:
        messages = [
            {"role": "system", "content": _GENERATE_SYSTEM},
            {"role": "user", "content": message},
        ]
        raw = get_completion(messages, self.complexity)
        return _strip_fences(raw)

    def _build_interpret_messages(self, message: str, code: str, result: dict) -> list[dict]:
        output = re.sub(r'[A-Za-z0-9+/]{100,}={0,2}', '[dado binário omitido]', result.get('output', ''))
        chart_note = "Sim (imagem capturada e exibida)" if result.get('chart_b64') else "Não"
        user_content = (
            f"Pergunta original: {message}\n\n"
            f"Código executado:\n```python\n{code[:2000]}\n```\n\n"
            f"Output:\n{output[:1500]}\n\n"
            f"Gráfico gerado: {chart_note}\n\n"
            f"Erro: {result.get('error') or 'Nenhum'}"
        )
        return [
            {"role": "system", "content": _INTERPRET_SYSTEM},
            {"role": "user", "content": user_content},
        ]

    def process(self, message: str, session_id: str) -> str:
        code = self._generate_code(message)
        result = execute_code(code)
        messages = self._build_interpret_messages(message, code, result)
        return get_completion(messages, self.complexity)

    def stream(self, message: str, session_id: str) -> Generator:
        # Phase 1 — GENERATE
        yield {"progress": "🧠 Gerando código de análise..."}
        code = self._generate_code(message)
        yield {"progress": f"✅ Código gerado ({len(code.splitlines())} linhas)"}

        # Phase 2 — EXECUTE
        yield {"progress": "⚙️ Executando análise..."}
        result = execute_code(code)

        if not result["success"]:
            yield {"progress": f"❌ Erro na execução: {str(result.get('error', ''))[:120]}"}
        elif result.get("chart_b64"):
            yield {"progress": "📊 Gráfico gerado com sucesso"}

        # Phase 3 — INTERPRET
        yield {"progress": "📝 Interpretando resultados..."}

        if result.get("chart_b64"):
            yield {"chart": result["chart_b64"]}

        messages = self._build_interpret_messages(message, code, result)
        yield from stream_completion(messages, self.complexity)
