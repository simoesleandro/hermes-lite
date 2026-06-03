from .base import BaseAgent
from model_router import Complexity, get_completion
from services.syshealth_client import SysHealthClient
from db.database import Database


class SaudeAgent(BaseAgent):
    name = "saude"
    complexity = Complexity.SIMPLE
    system_prompt = (
        "Você é o assistente de saúde e performance do Leandro, 40 anos, Rio de Janeiro. "
        "Ele treina musculação com programa PPL registrado no Hevy, usa Amazfit Bip 6 (dados Zepp) "
        "e faz uso de Creatina, Whey Protein Dux e Tirzepatida. "
        "Registra diariamente: ingestão de água (ml), peso corporal (kg), treinos, sono e HRV. "
        "Responda de forma direta e orientada a dados — sem rodeios, sem introduções longas. "
        "Quando receber um registro (ex: '2L de água', 'peso 88kg'), confirme de forma curta e objetiva. "
        "Para dúvidas clínicas ou medicamentos, lembre que um profissional de saúde deve ser consultado. "
        "\n\n"
        "RESUMO DO DIA — quando o usuário perguntar sobre seu estado geral (ex: 'como estou?', "
        "'como foi o dia?', 'resumo do dia', 'o que tenho hoje'), siga estas regras obrigatórias:\n"
        "1. Apresente TODOS os campos disponíveis nos dados do SysHealth em formato de lista estruturada. "
        "Nunca omita campos silenciosamente — campos com valor nulo devem aparecer como 'não registrado'.\n"
        "2. Nunca responda com menos de 3 campos quando dados do SysHealth estiverem disponíveis.\n"
        "3. Metas diárias de referência do Leandro: água 3000ml, proteína 150g.\n"
        "4. Ao final do resumo, inclua uma observação curta e direta: o que está bem (meta atingida ou "
        "próxima) e o que precisa de atenção (ex: 'Água baixa — faltam 1200ml', "
        "'Proteína abaixo da meta — faltam 60g'). Seja específico com os números.\n"
        "\n"
        "Responda em português."
    )

    _client = SysHealthClient()

    def __init__(self, db: Database):
        super().__init__(db)

    def process(self, message: str, session_id: str) -> str:
        summary = self._client.get_health_summary()
        context = "" if summary.get("offline") else self._format_summary(summary)

        system = self.system_prompt
        if context:
            system += f"\n\n{context}"

        history = self.db.get_history_as_messages(self.name, session_id)
        messages = (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": message}]
        )
        return get_completion(messages, self.complexity)

    @staticmethod
    def _format_summary(s: dict) -> str:
        def val(v, unit="", fallback="—"):
            return f"{v}{unit}" if v is not None else fallback

        lines = [
            "Dados de hoje (SysHealth):",
            f"  Água:        {val(s.get('agua'), 'ml')}",
            f"  Peso:        {val(s.get('peso'), 'kg')}",
            f"  Sono:        {val(s.get('sono'))}",
            f"  Passos:      {val(s.get('passos'))}",
            f"  Treino:      {val(s.get('treino'))}",
            f"  Déficit:     {val(s.get('deficit'), ' kcal')}",
            f"  Proteína:    {val(s.get('proteina'), 'g')}",
            f"  Tirzepatida: {'✓ tomada' if s.get('tirzepatida') else '✗ não registrada'}",
        ]
        return "\n".join(lines)
