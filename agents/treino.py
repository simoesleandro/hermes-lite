import json
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
        "usa Amazfit Bip 6 para monitorar HRV, sono e PAI (dados Zepp), "
        "e faz uso de Creatina, Whey Protein Dux e Tirzepatida. "
        "Meta de frequência musculação: 4-5 sessões por semana.\n\n"

        "CARDIO:\n"
        "- Zone 2: 12% incline, 5.5 km/h, 40-50min, HR 120-140 bpm, meta 4x/semana\n"
        "- HIIT sprint intervals: 2x/semana\n"
        "- PR de corrida: pace 05:47 min/km\n"
        "- FC durante corrida NÃO está disponível via API — não mencionar\n\n"

        "MÉTRICAS DE RECUPERAÇÃO:\n"
        "- PAI (Personal Activity Intelligence): meta ≥ 100. Proxy de intensidade cardiovascular\n"
        "- Sono profundo: meta ≥ 90 min/noite — gargalo identificado\n"
        "- HRV: ≥ 35 ms = Bom | 25–34 ms = Médio | < 25 ms = Baixo (alerta overtraining)\n\n"

        "PRs DE FORÇA (referência para progressão):\n"
        "- Deadlift: 28 kg\n"
        "- Seated Row: 55 kg\n"
        "- Lat Pulldown: 50 kg\n"
        "- Incline Dumbbell Press: 20 kg/lado\n"
        "- Volume alvo por sessão: 2700–3000 kg\n\n"

        "Responda de forma direta e orientada a dados — sem rodeios, sem introduções longas. "
        "Analise progressão de carga, volume, frequência e recuperação com base nos dados reais. "
        "Alerte sobre sinais de overtraining: HRV baixo, sono profundo < 60 min, "
        "queda de desempenho ou alta frequência sem recuperação adequada. "
        "Sugira ajustes concretos baseados nos dados fornecidos.\n\n"
        "CRÍTICO: responda APENAS com dados fornecidos. "
        "Se um dado não estiver disponível, diga 'sem dados' — nunca suponha valores.\n\n"
        "Responda em português."
    )

    _client = SysHealthClient()

    def __init__(self, db: Database):
        super().__init__(db)

    def _build_messages(self, message: str, session_id: str) -> list[dict]:
        analise  = self._client.get_analise_treinos(dias=30)
        recentes = self._client.get_treinos_recentes(dias=7)
        corpo    = self._client.get_corpo(dias=90)
        sono     = self._client.get_sono(dias=14)
        corridas = self._client.get_corridas(dias=30)

        context = self._format_context(analise, recentes, corpo, sono, corridas)
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
    def _format_context(
        analise: dict,
        recentes: list,
        corpo: dict,
        sono: dict,
        corridas: dict,
    ) -> str:
        def v(val, unit="", fallback="—"):
            return f"{val}{unit}" if val is not None else fallback

        nr = "não registrado"
        sections = []

        # === ANÁLISE 30 DIAS ===
        if not analise.get("offline"):
            lines = ["=== ANÁLISE 30 DIAS ==="]
            lines.append(f"  Total treinos:      {v(analise.get('total_treinos'), fallback=nr)}")
            lines.append(f"  Volume total:       {v(analise.get('volume_total_kg'), 'kg', nr)}")
            lines.append(f"  Duração média:      {v(analise.get('duracao_media_min'), 'min', nr)}")
            lines.append(f"  Frequência semanal: {v(analise.get('treinos_por_semana'), 'x/sem', nr)}")
            sections.append("\n".join(lines))

        # === TREINOS RECENTES (7 dias) ===
        if recentes:
            lines = ["=== TREINOS RECENTES (7 dias) ==="]
            for t in recentes:
                data   = t.get("data") or t.get("date") or "?"
                titulo = t.get("titulo") or t.get("title") or t.get("tipo") or "?"
                duracao = v(t.get("duracao_min") or t.get("duracao") or t.get("duration_minutes"), "min")
                volume  = v(t.get("volume_kg") or t.get("volume"), "kg")
                lines.append(f"  {data} | {titulo} | {duracao} | vol: {volume}")

                # Parse exercicios_json
                raw_ex = t.get("exercicios_json") or t.get("exercicios") or []
                if isinstance(raw_ex, str):
                    try:
                        raw_ex = json.loads(raw_ex)
                    except Exception:
                        raw_ex = []
                for ex in raw_ex[:8]:  # limita a 8 exercícios por treino
                    nome = ex.get("nome") or ex.get("name") or "?"
                    series = ex.get("series") or ex.get("sets") or []
                    if series:
                        partes = []
                        for s in series:
                            reps  = s.get("reps") or s.get("repeticoes") or "?"
                            carga = s.get("carga") or s.get("weight_kg") or s.get("peso") or "?"
                            rpe   = s.get("rpe")
                            parte = f"{reps}x{carga}kg"
                            if rpe:
                                parte += f" RPE{rpe}"
                            partes.append(parte)
                        lines.append(f"    {nome}: {' | '.join(partes)}")
                    else:
                        carga_max = ex.get("carga_maxima") or ex.get("max_weight")
                        lines.append(f"    {nome}: {v(carga_max, 'kg')}")

            # Top exercícios da análise
            top = analise.get("top_exercicios") or []
            if top:
                lines.append("")
                lines.append("=== TOP EXERCÍCIOS ===")
                for ex in top:
                    nome  = ex.get("nome") or ex.get("name") or "?"
                    freq  = v(ex.get("frequencia") or ex.get("count"))
                    carga = v(ex.get("carga_maxima") or ex.get("max_weight"), "kg")
                    lines.append(f"  {nome}: {freq}x, máx {carga}")
            sections.append("\n".join(lines))

        # === COMPOSIÇÃO CORPORAL ===
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

        # === SONO E RECUPERAÇÃO (14 dias) ===
        if not sono.get("offline"):
            lines = ["=== SONO E RECUPERAÇÃO (14 dias) ==="]
            lines.append(f"  Média sono total:    {v(sono.get('media_sono_min') or sono.get('media_sono'), 'min')}")
            lines.append(f"  Média sono profundo: {v(sono.get('media_sono_profundo_min') or sono.get('media_sono_profundo'), 'min')} (meta: ≥90 min)")
            lines.append(f"  Média HRV:           {v(sono.get('hrv_medio') or sono.get('media_hrv'), 'ms')}")
            lines.append(f"  Média PAI:           {v(sono.get('pai_medio') or sono.get('media_pai'))} (meta: ≥100)")
            ultimos = sono.get("ultimos_7_dias") or sono.get("dias") or []
            if ultimos:
                lines.append("  Últimos 7 dias:")
                for d in ultimos:
                    data     = d.get("data") or "?"
                    total    = v(d.get("sono_total_min") or d.get("sono") or d.get("duracao"), "min")
                    profundo = v(d.get("sono_profundo_min") or d.get("sono_profundo"), "min")
                    hrv      = v(d.get("hrv") or d.get("hrv_ms"), "ms")
                    pai      = v(d.get("pai"))
                    lines.append(f"    {data}: total {total} | profundo {profundo} | HRV {hrv} | PAI {pai}")
            sections.append("\n".join(lines))

        # === CORRIDAS (30 dias) ===
        if not corridas.get("offline"):
            lines = ["=== CORRIDAS (30 dias) ==="]
            total_km  = corridas.get("total_km") or corridas.get("distancia_total")
            total_ses = corridas.get("total_sessoes") or corridas.get("sessoes")
            lines.append(f"  Total: {v(total_km, 'km')} em {v(total_ses, ' sessões')}")
            historico = corridas.get("historico") or corridas.get("sessoes_lista") or []
            if historico:
                for c in historico[-8:]:
                    data   = c.get("data") or "?"
                    dist   = v(c.get("distancia_km") or c.get("distancia"), "km")
                    cal    = v(c.get("calorias"), "kcal")
                    pace   = c.get("pace") or c.get("pace_medio")
                    linha  = f"    {data}: {dist}"
                    if pace:
                        linha += f" | pace {pace} min/km"
                    if cal != "—":
                        linha += f" | {cal}"
                    lines.append(linha)
            sections.append("\n".join(lines))

        return "\n\n".join(sections)
