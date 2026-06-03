from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from services.sentinela_client import SentinelaClient
from db.database import Database


class SentinelaAgent(BaseAgent):
    name = "sentinela"
    complexity = Complexity.MEDIUM
    system_prompt = (
        "Você é o agente Sentinela — analista de contratos públicos do município do Rio de Janeiro. "
        "Analisa dados extraídos do PNCP (Portal Nacional de Contratações Públicas) em busca de "
        "irregularidades, superfaturamento e concentração indevida de fornecedores. "
        "\n\n"
        "Metodologias que você conhece e cita quando relevante:\n"
        "- IQR (Intervalo Interquartil): detecta outliers de valor por categoria de contrato\n"
        "- Z-score: mede desvio estatístico em relação à média da categoria\n"
        "- Concentração de fornecedor: identifica quando um único fornecedor domina contratos de um órgão\n"
        "- Contratos sem licitação: inexigibilidade, emergência e dispensa acima dos limiares legais\n"
        "\n\n"
        "REGRAS DE RESPOSTA:\n"
        "1. Sempre cite valores em R$ formatados (ex: R$ 45.000.000,00)\n"
        "2. Seja direto e objetivo — este é um sistema de auditoria, não um assistente genérico\n"
        "3. Quando listar alertas, destaque a severidade (alta/média/baixa) e o motivo técnico\n"
        "4. Se perguntado sobre um fornecedor específico, busque contratos e aponte alertas associados\n"
        "5. Nunca especule além dos dados disponíveis — se não há dados, diga explicitamente\n"
        "6. Para perguntas gerais ('o que há de suspeito?', 'resumo'), apresente os alertas de "
        "maior severidade com valores e fornecedores envolvidos\n"
        "\n"
        "Responda em português."
    )

    _client = SentinelaClient()

    def __init__(self, db: Database):
        super().__init__(db)

    def _build_messages(self, message: str, session_id: str) -> list[dict]:
        resumo = self._client.get_resumo()
        context = "" if resumo.get("offline") else self._format_resumo(resumo)
        system = self.system_prompt + (f"\n\n{context}" if context else "")
        history = self.db.get_history_as_messages(self.name, session_id)
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(self, message: str, session_id: str) -> str:
        return get_completion(self._build_messages(message, session_id), self.complexity)

    def stream(self, message: str, session_id: str) -> Generator[str, None, None]:
        yield from stream_completion(self._build_messages(message, session_id), self.complexity)

    @staticmethod
    def _format_resumo(r: dict) -> str:
        def brl(v):
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if v else "—"

        lines = [
            "Base de dados Sentinela RJ (PNCP — Rio de Janeiro):",
            f"  Contratos monitorados: {r.get('contratos', '—')}",
            f"  Valor total contratado: {brl(r.get('valor_total'))}",
            f"  Alertas abertos:        {r.get('alertas_abertos', '—')}",
            f"  Fornecedores distintos: {r.get('fornecedores', '—')}",
            f"  Última coleta:          {r.get('ultima_coleta') or 'não registrada'}",
        ]
        return "\n".join(lines)
