"""Agente Radar — curadoria GitHub e digest diário."""

import os
from typing import Generator

from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion


class RadarAgent(BaseAgent):
    name = "radar"
    complexity = Complexity.MEDIUM
    system_prompt = (
        "Você é o Radar GitHub do Hermes Lite — curador autônomo de repositórios open source.\n"
        "Todo dia o sistema busca repos no GitHub, filtra os melhores para o Leandro "
        "(Python, Flask, MCP, agentes IA, RAG, self-hosted, automação Windows) e gera um documento com:\n"
        "- nota de 0 a 10\n"
        "- o que faz\n"
        "- como usar\n"
        "- raciocínio da curadoria\n\n"
        "Use o digest do dia (se disponível) como fonte principal.\n"
        "Comandos que o backend processa:\n"
        "- 'gerar radar' / 'radar agora' → dispara curadoria\n"
        "- 'último radar' / 'radar de hoje' → mostra resumo\n\n"
        "Tom: direto, útil, sem hype. Responda em português."
    )

    def _try_radar_action(self, message: str) -> str | None:
        msg = message.strip().lower()
        if any(k in msg for k in ("gerar radar", "radar agora", "atualizar radar", "rodar radar")):
            if os.getenv("GITHUB_RADAR_ENABLED", "1") != "1":
                return "Radar GitHub desligado (GITHUB_RADAR_ENABLED=0)."
            from services.github_radar import run_github_radar
            result = run_github_radar(self.db, notify=False)
            if result.get("already_exists"):
                return f"Radar de {result['date']} já existe ({result['picks_count']} repos). Use GITHUB_RADAR_FORCE=1 para regerar."
            if result.get("skipped"):
                return "Radar desabilitado."
            n = result.get("picks_count", 0)
            return f"✅ Radar gerado — {n} repositório(s). Arquivo: {result.get('markdown_path', 'exports/github-radar')}"

        if any(k in msg for k in ("último radar", "radar de hoje", "radar hoje", "digest radar")):
            digest = self.db.get_latest_github_digest()
            if not digest:
                return "Nenhum digest Radar ainda. Diga «gerar radar» ou aguarde o Cronos (manhã)."
            return self._format_digest_summary(digest)

        return None

    @staticmethod
    def _format_digest_summary(digest: dict) -> str:
        picks = digest.get("picks") or []
        date = digest.get("date", "?")
        if not picks:
            return f"Radar {date}: nenhum pick registrado."
        lines = [f"📡 Radar GitHub — {date}", ""]
        for p in picks:
            lines.append(f"**{p.get('full_name')}** — {p.get('nota', 0)}/10")
            lines.append(f"  {p.get('o_que_faz', '')}")
            lines.append(f"  Como usar: {p.get('como_usar', '')[:200]}")
            lines.append("")
        return "\n".join(lines)

    def _digest_context(self) -> str:
        digest = self.db.get_latest_github_digest()
        if not digest:
            return ""
        md = digest.get("markdown") or ""
        if len(md) > 6000:
            md = md[:6000] + "\n… (truncado)"
        return f"\n\n=== DIGEST RADAR MAIS RECENTE ({digest.get('date')}) ===\n{md}"

    def _build_messages(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> list[dict]:
        action = self._try_radar_action(message)
        system = (
            self.system_prompt
            + self._digest_context()
            + self._facts_block()
            + self._memory_block(conversation_id)
        )
        if action:
            system += f"\n\n[Ação Radar executada: {action}]"
        history = self._get_history(session_id, conversation_id)
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        quick = self._try_radar_action(message)
        if quick:
            return quick
        return get_completion(
            self._build_messages(message, session_id, conversation_id=conversation_id),
            self.complexity,
        )

    def stream(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> Generator:
        quick = self._try_radar_action(message)
        if quick:
            yield quick
            return
        yield from stream_completion(
            self._build_messages(message, session_id, conversation_id=conversation_id),
            self.complexity,
        )
