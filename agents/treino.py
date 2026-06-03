from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from services.syshealth_client import SysHealthClient
from db.database import Database


class TreinoAgent(BaseAgent):
    name = "treino"
    complexity = Complexity.MEDIUM
    system_prompt = (
        "Você é o coach de treino e performance do Leandro, 40 anos, Rio de Janeiro. "
        "Ele treina musculação com programa PPL (Push/Pull/Legs) registrado no Hevy, "
        "usa Amazfit Bip 6 para monitorar HRV e sono (dados Zepp), "
        "e faz uso de Creatina, Whey Protein Dux e Tirzepatida. "
        "Meta de frequência: 4-5 sessões por semana.\n\n"
        "Responda de forma direta e orientada a dados — sem rodeios, sem introduções longas. "
        "Analise progressão de carga, volume, frequência e recuperação com base nos dados reais. "
        "Alerte sobre sinais de overtraining: HRV baixo (< 40ms), sono insuficiente (< 6h), "
        "queda de desempenho ou alta frequência sem recuperação adequada. "
        "Sugira ajustes concretos baseados nos dados fornecidos. "
        "Ao responder sobre exercícios ou cargas, use apenas os dados do contexto — "
        "nunca invente cargas, séries ou exercícios não presentes nos dados.\n\n"
        "CRÍTICO: responda APENAS com dados fornecidos. "
        "Se um dado não estiver disponível, diga 'sem dados' — nunca suponha valores.\n\n"
        "Responda em português."
    )

    _client = SysHealthClient()

    def __init__(self, db: Database):
        super().__init__(db)

    def _build_messages(self, message: str, session_id: str) -> list[dict]:
        analise = self._client.get_analise_treinos(dias=30)
        recentes = self._client.get_treinos_recentes(dias=7)
        corpo = self._client.get_corpo(dias=90)
        sono = self._client.get_sono(dias=14)

        context = self._format_context(analise, recentes, corpo, sono)
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
    def _format_context(analise: dict, recentes: list, corpo: dict, sono: dict) -> str:
        def v(val, unit="", fallback="—"):
            return f"{val}{unit}" if val is not None else fallback

        sections = []

        if not analise.get("offline"):
            nr = "não registrado"
            lines = ["=== ANÁLISE 30 DIAS ==="]
            lines.append(f"  Total treinos:      {v(analise.get('total_treinos'), fallback=nr)}")
            lines.append(f"  Volume total:       {v(analise.get('volume_total_kg'), 'kg', nr)}")
            lines.append(f"  Duração média:      {v(analise.get('duracao_media_min'), 'min', nr)}")
            lines.append(f"  Frequência semanal: {v(analise.get('treinos_por_semana'), 'x/sem', nr)}")
            sections.append("\n".join(lines))

        if recentes:
            lines = ["=== TREINOS RECENTES (7 dias) ==="]
            for t in recentes:
                data = t.get("data") or t.get("date") or "?"
                titulo = t.get("titulo") or t.get("title") or t.get("tipo") or "?"
                duracao = v(t.get("duracao_min") or t.get("duracao") or t.get("duration_minutes"), "min")
                volume = v(t.get("volume_kg") or t.get("volume"), "kg")
                lines.append(f"  {data} | {titulo} | {duracao} | vol: {volume}")

            top = analise.get("top_exercicios") or []
            if top:
                lines.append("")
                lines.append("=== TOP EXERCÍCIOS ===")
                for ex in top:
                    nome = ex.get("nome") or ex.get("name") or "?"
                    freq = v(ex.get("frequencia") or ex.get("count"))
                    carga = v(ex.get("carga_maxima") or ex.get("max_weight"), "kg")
                    lines.append(f"  {nome}: {freq}x, máx {carga}")
            sections.append("\n".join(lines))

        if not corpo.get("offline"):
            lines = ["=== COMPOSIÇÃO CORPORAL ==="]
            lines.append(f"  Peso atual: {v(corpo.get('peso_atual'), 'kg')}")
            lines.append(f"  Variação:   {v(corpo.get('variacao'), 'kg')}")
            historico = corpo.get("historico") or []
            if historico:
                entradas = historico[-5:]
                hist_str = " → ".join(
                    f"{h.get('data', '?')}: {v(h.get('peso'), 'kg')}" for h in entradas
                )
                lines.append(f"  Histórico:  {hist_str}")
            sections.append("\n".join(lines))

        if not sono.get("offline"):
            lines = ["=== SONO E RECUPERAÇÃO ==="]
            lines.append(f"  Média sono: {v(sono.get('media_sono'), 'h')}")
            lines.append(f"  HRV médio:  {v(sono.get('hrv_medio'), 'ms')}")
            ultimos = sono.get("ultimos_7_dias") or []
            if ultimos:
                lines.append("  Últimos 7 dias:")
                for d in ultimos:
                    data = d.get("data") or "?"
                    dur = v(d.get("sono") or d.get("duracao"), "h")
                    hrv = v(d.get("hrv"), "ms")
                    lines.append(f"    {data}: sono {dur}, HRV {hrv}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)
