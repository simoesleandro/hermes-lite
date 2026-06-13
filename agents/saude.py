import re
from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from services.syshealth_client import SysHealthClient
from db.database import Database

_AGUA_RE = re.compile(
    r"(?:bebi|registrei|tomei|adicionei)\s+"
    r"(?:(\d+(?:[.,]\d+)?)\s*(?:l|litros?)|(\d+)\s*(?:ml|mL))",
    re.I,
)
_PESO_RE = re.compile(
    r"(?:peso|pesando|estou\s+com)\s*(?:de|é|:)?\s*(\d+(?:[.,]\d+)?)\s*kg",
    re.I,
)
_TIRZE_RE = re.compile(
    r"(?:tomei|apliquei|registrei)\s+(?:a\s+)?(?:tirzepatida|mounjaro)|"
    r"tirzepatida\s+(?:tomada|aplicada|hoje)",
    re.I,
)


class SaudeAgent(BaseAgent):
    name = "saude"
    complexity = Complexity.SIMPLE
    system_prompt = (
        "Você é o assistente de saúde e performance do Leandro. Responda em português, "
        "de forma direta e orientada a dados — sem rodeios, sem introduções longas.\n\n"

        "=== PERFIL ===\n"
        "Leandro Simões, 40 anos, Rio de Janeiro.\n"
        "Peso atual: 92,9 kg | Meta: 83 kg | Faltam: ~10 kg\n"
        "Gordura corporal: 29,8% | Massa muscular: 61,8 kg (preservar acima de 61 kg)\n"
        "HRV médio: 35 ms (meta: 45+) | Gordura visceral: nível 13 (meta: <10)\n"
        "Água corporal: 50% (meta: 55%) | TMB: 1.773 kcal\n\n"

        "=== TREINO — PPL 6x/semana ===\n"
        "- Treino A (Push): Segunda e Quinta\n"
        "- Treino B (Pull): Terça e Sexta\n"
        "- Treino C (Legs): Quarta e Sábado\n"
        "- Cardio: Zona 2 (4x/semana, FC 120-140 bpm) + HIIT (2x/semana)\n\n"

        "=== PROTOCOLO HRV DO DIA ===\n"
        "- HRV >= 45: Treino completo + HIIT 5 tiros 11 km/h\n"
        "- HRV 37-44: Treino completo, intensidade normal\n"
        "- HRV 33-36: RPE máx 8.5, HIIT 4 tiros 10 km/h\n"
        "- HRV 30-32: 3 séries máx por exercício, HIIT substituído por Zona 2\n"
        "- HRV < 30: Cancelar musculação\n\n"

        "=== NUTRIÇÃO (metas diárias) ===\n"
        "Calorias: 1.850-1.950 kcal | Proteína: 180-190 g\n"
        "Carboidratos: 150-170 g | Gordura: 60-70 g | Água: 3 L/dia\n\n"

        "=== SUPLEMENTAÇÃO ===\n"
        "Whey Dux, Creatina Creapure 5 g pós-treino (inclusive dias de descanso), "
        "Magnésio Trio (antes de dormir), D3+K2, Omega-3 Omegafor Plus, Pré-treino More Dux\n\n"

        "=== PRs ATUAIS (Jun/2026) ===\n"
        "Remada 55 kg, Puxada 45 kg, Crucifixo 55 kg, "
        "Supino Barra 18-19 kg, Leg Press 80 kg\n\n"

        "=== GARGALO PRINCIPAL ===\n"
        "Sono irregular (regularidade 74-80%). Meta: dormir até 22h30.\n\n"

        "=== COMPORTAMENTO ===\n"
        "- Registro de água (ex: '2L de água'): confirmar e calcular quanto falta para 3L\n"
        "- HRV do dia: indicar o protocolo de treino correspondente\n"
        "- Peso: comparar com tendência e distância da meta de 83 kg\n"
        "- Treino registrado: confirmar; destacar se houver PR\n"
        "- Para perguntas sobre estado geral ('como estou?', 'resumo do dia'): "
        "apresentar TODOS os campos dos dados SysHealth — nunca omitir campos nulos "
        "(mostrar como 'não registrado'). Nunca responder com menos de 3 campos quando "
        "dados estiverem disponíveis. Encerrar com observação direta sobre o que está bem "
        "e o que precisa de atenção, com números específicos.\n"
        "- Para dúvidas clínicas ou sobre medicamentos: indicar que um profissional de saúde "
        "deve ser consultado."
    )

    _client = SysHealthClient()

    def __init__(self, db: Database):
        super().__init__(db)

    def _try_register(self, message: str) -> str | None:
        """Detecta intents de registro e persiste no SysHealth. Retorna nota para o prompt."""
        m = _AGUA_RE.search(message)
        if m:
            litros = m.group(1)
            ml_raw = m.group(2)
            if litros:
                ml = int(float(litros.replace(",", ".")) * 1000)
            else:
                ml = int(ml_raw)
            result = self._client.register_agua(ml)
            if result["ok"]:
                summary = self._client.get_health_summary()
                total = summary.get("agua_hoje_ml") or ml
                falta = max(0, 3000 - (total or 0))
                return (
                    f"[REGISTRO AUTOMÁTICO] Água +{ml} ml registrada no SysHealth. "
                    f"Total hoje: {total} ml. Faltam {falta} ml para a meta de 3 L."
                )
            return f"[REGISTRO FALHOU] Não foi possível registrar água: {result.get('error')}"

        m = _PESO_RE.search(message)
        if m:
            kg = float(m.group(1).replace(",", "."))
            result = self._client.register_peso(kg)
            if result["ok"]:
                diff = round(kg - 83, 1)
                return (
                    f"[REGISTRO AUTOMÁTICO] Peso {kg} kg registrado no SysHealth. "
                    f"Distância da meta (83 kg): {diff:+.1f} kg."
                )
            return f"[REGISTRO FALHOU] Não foi possível registrar peso: {result.get('error')}"

        if _TIRZE_RE.search(message):
            result = self._client.register_tirzepatida()
            if result["ok"]:
                return "[REGISTRO AUTOMÁTICO] Tirzepatida marcada como tomada hoje no SysHealth."
            return f"[REGISTRO FALHOU] Não foi possível registrar tirzepatida: {result.get('error')}"

        return None

    def _build_messages(
        self, message: str, session_id: str, image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> list[dict]:
        registro = self._try_register(message)
        summary = self._client.get_health_summary()
        context = "" if summary.get("offline") else self._format_summary(summary)
        system = self.system_prompt + self._memory_block(conversation_id)
        if registro:
            system += f"\n\n{registro}"
        if context:
            system += f"\n\n{context}"
        history = self._get_history(session_id, conversation_id)
        if image_b64:
            mime_type = "image/jpeg"
            data = image_b64
            if image_b64.startswith("data:"):
                prefix, _, data = image_b64.partition(",")
                mime_type = prefix.split(":")[1].split(";")[0]
            user_content: list = [
                {"type": "image", "mime_type": mime_type, "data": data},
                {"type": "text", "text": message},
            ]
        else:
            user_content = message
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": user_content}]
        )

    def process(
        self, message: str, session_id: str, image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        complexity = Complexity.HEAVY if image_b64 else self.complexity
        return get_completion(
            self._build_messages(message, session_id, image_b64, conversation_id), complexity,
        )

    def stream(
        self, message: str, session_id: str, image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> Generator[str, None, None]:
        complexity = Complexity.HEAVY if image_b64 else self.complexity
        yield from stream_completion(
            self._build_messages(message, session_id, image_b64, conversation_id), complexity,
        )

    @staticmethod
    def _format_summary(s: dict) -> str:
        def val(v, unit="", fallback="—"):
            return f"{v}{unit}" if v is not None else fallback

        lines = [
            "Dados de hoje (SysHealth):",
            f"  Água:        {val(s.get('agua_hoje_ml'), ' ml')}",
            f"  Peso:        {val(s.get('peso_kg'), ' kg')}",
            f"  Sono:        {val(s.get('sono_horas'), ' h')}",
            f"  Passos:      {val(s.get('passos_hoje'))}",
            f"  Treino:      {val(s.get('treino_hoje'))}",
            f"  Déficit:     {val(s.get('deficit_calorico'), ' kcal')}",
            f"  Proteína:    {val(s.get('proteina_g'), ' g')}",
            f"  Carboidrato: {val(s.get('carboidrato_g'), ' g')}",
            f"  HRV:         {val(s.get('hrv'), ' ms')}",
            f"  Fadiga:      {val(s.get('fadiga'))}",
            f"  Tirzepatida: {'✓ tomada' if s.get('tirzepatida_hoje') else '✗ não registrada'}",
        ]
        return "\n".join(lines)
