from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from services.sentinela_client import SentinelaClient
from db.database import Database


_ARTIGOS = """=== ARTIGOS DE REFERÊNCIA — LEI 14.133/2021 ===

Art. 6º, XXIII — Define licitação deserta e fracassada
Art. 28 — Modalidades: Pregão, Concorrência, Concurso, Leilão, Diálogo Competitivo
Art. 74 — Inexigibilidade de licitação:
  caput: quando inviável a competição
  I: aquisição de materiais/serviços com fornecedor exclusivo
  II: contratação de profissional do setor artístico
  III: contratação de serviços técnicos especializados
Art. 75 — Dispensa de licitação (rol taxativo):
  I: valor até R$ 50.000 obras/serviços engenharia
  II: valor até R$ 25.000 outros serviços/compras
  VIII: emergência ou calamidade pública
Art. 89 — Vedação ao fracionamento de despesa
Art. 92 — Critérios de julgamento das propostas
Art. 145 — Crimes em licitações:
  I: frustrar ou fraudar o caráter competitivo
  II: impedir, perturbar ou fraudar ato de licitação
Art. 178 — Responsabilidade administrativa dos agentes

=== ARTIGOS DE REFERÊNCIA — LEI 8.666/1993 ===
Art. 24 — Dispensa de licitação (rol taxativo histórico)
Art. 25 — Inexigibilidade (referência para contratos anteriores)"""


class JuridicoAgent(BaseAgent):
    name = "juridico"
    complexity = Complexity.HEAVY
    system_prompt = (
        "Você é um especialista em Direito Administrativo e licitações públicas, "
        "com foco na Lei 14.133/2021 (Nova Lei de Licitações) e Lei 8.666/1993. "
        "Analisa contratos do município do Rio de Janeiro usando dados reais do sistema Sentinela RJ.\n\n"
        "Responda de forma direta e fundamentada — cite sempre o dispositivo legal aplicável "
        "(artigo, inciso, parágrafo). "
        "Quando analisar um contrato específico, indique:\n"
        "1. O enquadramento legal\n"
        "2. Se há irregularidade formal ou material\n"
        "3. O risco jurídico (baixo/médio/alto)\n"
        "4. A recomendação (investigar/encaminhar TCM-RJ/arquivar)\n\n"
        "CRÍTICO: Nunca invente artigos ou dispositivos legais. "
        "Use apenas os artigos fornecidos neste contexto. "
        "Se não souber a resposta com certeza, diga explicitamente. "
        "Para questões fora do direito administrativo, indique que está fora do seu escopo.\n\n"
        "Responda em português.\n\n"
        + _ARTIGOS
    )

    _client = SentinelaClient()

    def __init__(self, db: Database):
        super().__init__(db)

    def _build_messages(self, message: str, session_id: str) -> list[dict]:
        resumo = self._client.get_resumo()
        alertas = self._client.get_alertas(severidade="alta", limit=10)

        if resumo.get("offline"):
            context = "[Banco Sentinela offline — dados de contratos indisponíveis]"
        else:
            context = self._format_context(resumo, alertas)

        system = self.system_prompt + f"\n\n=== DADOS REAIS DO SENTINELA RJ ===\n{context}"
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
    def _format_context(cls, resumo: dict, alertas: list) -> str:
        brl = cls._brl
        lines = [
            f"Contratos monitorados: {resumo.get('contratos', '—')}",
            f"Valor total contratado: {brl(resumo.get('valor_total'))}",
            f"Alertas abertos:        {resumo.get('alertas_abertos', '—')}",
            f"Última coleta:          {resumo.get('ultima_coleta') or 'não registrada'}",
            "",
            "Alertas de alta severidade:",
        ]

        if not alertas:
            lines.append("(nenhum alerta de alta severidade)")
        else:
            for i, a in enumerate(alertas, 1):
                lines.append(f"{i}. {a.get('tipo', '—')}")
                lines.append(f"   Fornecedor: {a.get('fornecedor') or '—'}")
                lines.append(f"   Valor:      {brl(a.get('valor'))}")
                lines.append(f"   Data:       {a.get('data') or '—'}")
                desc = (a.get("descricao") or "").replace("\n", " ")
                lines.append(f"   Descrição:  {desc}")
                metod = (a.get("metodologia") or "").replace("\n", " ")
                if metod:
                    lines.append(f"   Metodologia: {metod}")

        return "\n".join(lines)
