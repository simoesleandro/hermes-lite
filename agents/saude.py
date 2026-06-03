from .base import BaseAgent
from model_router import Complexity, get_completion
from services.syshealth_client import SysHealthClient


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
        "Responda em português."
    )

    _client = SysHealthClient()

    def process(self, message: str) -> str:
        summary = self._client.get_health_summary()
        context = "" if summary.get("offline") else self._format_summary(summary)

        prompt = self.system_prompt
        if context:
            prompt += f"\n\n{context}"
        prompt += f"\n\nUsuário: {message}"

        return get_completion(prompt, self.complexity)

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
