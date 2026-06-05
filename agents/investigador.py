import json
import re
from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from services.investigador_tools import TOOLS_REGISTRY
from db.database import Database


_PLAN_SYSTEM = """Você é um investigador de contratos públicos.
Analise a pergunta do usuário e decida quais ferramentas usar para investigar.

Ferramentas disponíveis:
- buscar_cnpj: recebe um CNPJ — retorna dados cadastrais da empresa
- buscar_contratos: recebe um termo (nome ou CNPJ) — busca contratos no banco Sentinela RJ
- buscar_alertas: recebe um termo (nome ou CNPJ) — busca alertas de irregularidade
- buscar_web: recebe uma query — busca notícias e informações públicas na web

Responda APENAS com JSON válido, sem markdown, sem explicação adicional:
{
  "plano": "descrição em 1 linha do que vai investigar",
  "ferramentas": [
    {"nome": "buscar_cnpj", "parametro": "00.000.000/0001-00"},
    {"nome": "buscar_contratos", "parametro": "termo de busca"},
    {"nome": "buscar_alertas", "parametro": "termo de busca"},
    {"nome": "buscar_web", "parametro": "query para busca na web"}
  ]
}"""


_SYNTHESIZE_SYSTEM = """Você é um investigador especialista em contratos públicos e compliance.
Com base nos dados coletados, gere um dossiê investigativo estruturado.
Use APENAS os dados fornecidos. Nunca invente informações.
Se não houver dados suficientes, diga explicitamente.
Responda em português."""


class InvestigadorAgent(BaseAgent):
    name = "investigador"
    complexity = Complexity.HEAVY

    def __init__(self, db: Database):
        super().__init__(db)

    def _plan(self, message: str) -> dict:
        messages = [
            {"role": "system", "content": _PLAN_SYSTEM},
            {"role": "user", "content": message},
        ]
        try:
            raw = get_completion(messages, self.complexity)
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
            plan = json.loads(raw)
            if "ferramentas" not in plan:
                raise ValueError("missing ferramentas")
            return plan
        except Exception:
            return {
                "plano": f"Investigação geral sobre: {message[:80]}",
                "ferramentas": [
                    {"nome": "buscar_contratos", "parametro": message[:100]},
                    {"nome": "buscar_web", "parametro": f"{message[:80]} Rio de Janeiro contrato público"},
                ],
            }

    def _build_synthesize_messages(self, question: str, resultados: dict) -> list[dict]:
        parts = [f"PERGUNTA ORIGINAL: {question}\n\nDADOS COLETADOS:"]
        for tool_name, result in resultados.items():
            parts.append(f"\n--- {tool_name.upper()} ---")
            parts.append(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        user_content = "\n".join(parts) + (
            "\n\nCom base nos dados acima, estruture o relatório com:\n"
            "## Identificação\n"
            "## Contratos Encontrados\n"
            "## Alertas e Irregularidades\n"
            "## Informações Públicas\n"
            "## Análise de Risco (Baixo/Médio/Alto)\n"
            "## Recomendação"
        )
        return [
            {"role": "system", "content": _SYNTHESIZE_SYSTEM},
            {"role": "user", "content": user_content},
        ]

    def process(self, message: str, session_id: str, image_b64: str | None = None) -> str:
        plano = self._plan(message)
        resultados = {}
        for ferramenta in plano.get("ferramentas", []):
            nome = ferramenta.get("nome")
            param = ferramenta.get("parametro", "")
            if nome in TOOLS_REGISTRY:
                try:
                    resultados[nome] = TOOLS_REGISTRY[nome](param)
                except Exception as exc:
                    resultados[nome] = {"erro": str(exc)}
        return get_completion(self._build_synthesize_messages(message, resultados), self.complexity)

    def stream(self, message: str, session_id: str, image_b64: str | None = None) -> Generator:
        # Phase 1 — PLAN
        yield {"progress": "🔍 Analisando pergunta e planejando investigação..."}
        plano = self._plan(message)
        yield {"progress": f"📋 Plano: {plano['plano']}"}

        # Phase 2 — EXECUTE
        resultados = {}
        for ferramenta in plano.get("ferramentas", []):
            nome = ferramenta.get("nome")
            param = ferramenta.get("parametro", "")
            if nome not in TOOLS_REGISTRY:
                continue
            yield {"progress": f"⚙️ Executando {nome}({param[:50]})..."}
            try:
                resultados[nome] = TOOLS_REGISTRY[nome](param)
                yield {"progress": f"✅ {nome} concluído"}
            except Exception as exc:
                resultados[nome] = {"erro": str(exc)}
                yield {"progress": f"⚠️ {nome} falhou: {str(exc)[:60]}"}

        # Phase 3 — SYNTHESIZE
        yield {"progress": "✍️ Gerando relatório investigativo..."}
        messages = self._build_synthesize_messages(message, resultados)
        yield from stream_completion(messages, self.complexity)
