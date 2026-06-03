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
  Tabelas: contratos(objeto, valor_global, data_assinatura,
  fornecedor_ni, categoria_processo_nome),
  alertas(tipo, severidade, descricao, valor_referencia),
  fornecedores(ni, razao_social)

- SYSHEALTH_DB: SQLite com dados de saúde pessoal
  Tabelas: refeicoes(calorias, proteinas, carboidratos, gorduras, data_hora),
  agua(quantidade_ml, data_hora), medidas(peso, data),
  amazfit_dados(passos, sono_total_min, hrv_ms, data_hora),
  hevy_treinos(titulo, duracao_min, volume_kg, data_hora)

Libs disponíveis: pandas, numpy, matplotlib, seaborn, sqlite3,
json, datetime, math, statistics, collections, itertools, re, csv

Para gráficos: use matplotlib ou seaborn.
Ao final SEMPRE chame: chart_b64 = save_chart()
e imprima: print(chart_b64)

Para dados tabulares: use print() com formatação clara.

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
        user_content = (
            f"Pergunta original: {message}\n\n"
            f"Código executado:\n```python\n{code[:2000]}\n```\n\n"
            f"Output:\n{result.get('output', '')[:3000]}\n\n"
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
