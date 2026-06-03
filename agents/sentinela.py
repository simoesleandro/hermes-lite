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
        "4. Se perguntado sobre um fornecedor específico, indique os contratos e alertas presentes "
        "nos dados fornecidos\n"
        "5. Para perguntas gerais ('o que há de suspeito?', 'resumo'), apresente os alertas de "
        "maior severidade com valores e fornecedores dos dados abaixo\n"
        "\n\n"
        "CRÍTICO: Responda APENAS com dados das seções RESUMO GERAL, ALERTAS REAIS e TOP CONTRATOS "
        "fornecidas abaixo no contexto do sistema. "
        "NUNCA invente fornecedores, valores ou contratos. "
        "Se não tiver a informação nos dados fornecidos, diga exatamente: "
        "'não tenho esse dado no banco atual'.\n"
        "\n"
        "Responda em português."
    )

    _client = SentinelaClient()

    def __init__(self, db: Database):
        super().__init__(db)

    def _build_messages(self, message: str, session_id: str) -> list[dict]:
        resumo = self._client.get_resumo()
        alertas = self._client.get_alertas(limit=20)
        top = self._client.top_contratos(limit=5)

        if resumo.get("offline"):
            context = "[Banco Sentinela offline — sem dados disponíveis]"
        else:
            context = self._format_context(resumo, alertas, top)

        system = self.system_prompt + f"\n\n{context}"
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
    def _brl(v) -> str:
        if v is None:
            return "—"
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @classmethod
    def _format_context(cls, resumo: dict, alertas: list, top: list) -> str:
        brl = cls._brl
        lines = [
            "=== RESUMO GERAL ===",
            f"Contratos monitorados: {resumo.get('contratos', '—')}",
            f"Valor total contratado: {brl(resumo.get('valor_total'))}",
            f"Alertas abertos:        {resumo.get('alertas_abertos', '—')}",
            f"Fornecedores distintos: {resumo.get('fornecedores', '—')}",
            f"Última coleta:          {resumo.get('ultima_coleta') or 'não registrada'}",
            "",
            "=== ALERTAS REAIS (dados do banco) ===",
        ]

        if not alertas:
            lines.append("(nenhum alerta disponível)")
        else:
            for i, a in enumerate(alertas, 1):
                lines.append(
                    f"{i}. [{a.get('severidade', '?').upper()}] {a.get('tipo', '—')}"
                )
                lines.append(f"   Fornecedor: {a.get('fornecedor') or '—'}")
                lines.append(f"   Valor:      {brl(a.get('valor'))}")
                lines.append(f"   Data:       {a.get('data') or '—'}")
                desc = (a.get('descricao') or '').replace('\n', ' ')
                lines.append(f"   Descrição:  {desc}")

        lines += [
            "",
            "=== TOP CONTRATOS POR VALOR ===",
        ]

        if not top:
            lines.append("(nenhum contrato disponível)")
        else:
            for i, c in enumerate(top, 1):
                lines.append(
                    f"{i}. {brl(c.get('valor'))} — {c.get('fornecedor') or '—'}"
                )
                obj = (c.get('objeto') or '').strip()
                lines.append(f"   Objeto:   {obj[:120]}{'…' if len(obj) > 120 else ''}")
                lines.append(f"   Data:     {c.get('data_assinatura') or '—'}")
                lines.append(f"   Alertas:  {c.get('alertas', 0)}")

        return "\n".join(lines)
