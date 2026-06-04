import re
import subprocess
import time
from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from db.database import Database

_SERVICES = {
    "cronos":    "HermesCronos",
    "vigia":     "HermesVigia",
    "syshealth": "HermesSysHealthAPI",
    "hermes":    "HermesLite",
}

_ALL_SERVICES = ["HermesCronos", "HermesVigia", "HermesSysHealthAPI", "HermesLite"]

_ACTIONS = {
    "ativar":    "start",
    "iniciar":   "start",
    "ligar":     "start",
    "parar":     "stop",
    "desligar":  "stop",
    "reiniciar": "restart",
    "restart":   "restart",
}

_ACT_RE = re.compile(
    r'\b(ativar|iniciar|ligar|parar|desligar|reiniciar|restart)\b',
    re.I,
)
_SVC_RE    = re.compile(r'\b(cronos|vigia|syshealth|hermes)\b', re.I)
_STATUS_RE = re.compile(
    r'\b(status|estado|online|offline|rodando|ativo|parado|qual\s+servi|como\s+est[áa])\b',
    re.I,
)

_SYSTEM = (
    "Você é o agente de operações do Hermes Lite. "
    "Confirme ações executadas nos serviços Windows e explique o resultado. "
    "Seja direto e objetivo. Responda em português."
)


def _run_sc(action: str, service: str) -> dict:
    if action == "restart":
        r1 = subprocess.run(["sc", "stop",  service], capture_output=True, text=True, timeout=15)
        time.sleep(2)
        r2 = subprocess.run(["sc", "start", service], capture_output=True, text=True, timeout=15)
        return {
            "ok":     r2.returncode == 0,
            "stdout": f"[stop]  {r1.stdout.strip()}\n[start] {r2.stdout.strip()}",
            "stderr": " | ".join(filter(None, [r1.stderr.strip(), r2.stderr.strip()])),
        }
    r = subprocess.run(["sc", action, service], capture_output=True, text=True, timeout=15)
    return {"ok": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}


def _query_all_status() -> list[dict]:
    results = []
    for svc in _ALL_SERVICES:
        r = subprocess.run(["sc", "query", svc], capture_output=True, text=True, timeout=10)
        m = re.search(r'STATE\s*:\s*\d+\s+(\w+)', r.stdout)
        state = m.group(1) if m else ("RUNNING" if r.returncode == 0 else "STOPPED")
        results.append({"service": svc, "state": state, "ok": r.returncode == 0})
    return results


def _format_status(statuses: list[dict]) -> str:
    lines = ["Status dos servicos Windows:"]
    for s in statuses:
        icon = "🟢" if s["state"] == "RUNNING" else "🔴"
        lines.append(f"  {icon} {s['service']}: {s['state']}")
    return "\n".join(lines)


def _parse(message: str) -> tuple[str | None, str | None]:
    if _STATUS_RE.search(message) and not _ACT_RE.search(message):
        return "status", None
    am = _ACT_RE.search(message)
    sm = _SVC_RE.search(message)
    action  = _ACTIONS.get(am.group(1).lower()) if am else None
    service = _SERVICES.get(sm.group(1).lower()) if sm else None
    return action, service


def _make_context(message: str, action: str, service: str, result: dict) -> str:
    return (
        f"Pedido: {message}\n"
        f"Comando: sc {action} {service}\n"
        f"Resultado: {'sucesso' if result['ok'] else 'falhou'}\n"
        f"Output: {result['stdout'][:400] or '(vazio)'}\n"
        f"Stderr: {result['stderr'][:200] or 'nenhum'}"
    )


class OpsAgent(BaseAgent):
    name       = "ops"
    complexity = Complexity.SIMPLE
    system_prompt = _SYSTEM

    def __init__(self, db: Database):
        super().__init__(db)

    def process(self, message: str, session_id: str) -> str:
        action, service = _parse(message)

        if action == "status":
            statuses = _query_all_status()
            messages = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": f"Pedido: {message}\n\n{_format_status(statuses)}"},
            ]
            return get_completion(messages, self.complexity)

        if not action or not service:
            return get_completion(self._build_messages(message, session_id), self.complexity)

        result = _run_sc(action, service)
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _make_context(message, action, service, result)},
        ]
        return get_completion(messages, self.complexity)

    def stream(self, message: str, session_id: str) -> Generator:
        action, service = _parse(message)

        if action == "status":
            yield {"progress": "🔍 Consultando status dos serviços..."}
            statuses = _query_all_status()
            yield {"progress": _format_status(statuses).replace("\n", " | ")}
            messages = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": f"Pedido: {message}\n\n{_format_status(statuses)}"},
            ]
            yield from stream_completion(messages, self.complexity)
            return

        if not action or not service:
            yield from stream_completion(self._build_messages(message, session_id), self.complexity)
            return

        yield {"progress": f"⚙️ Executando: sc {action} {service}..."}
        result = _run_sc(action, service)
        yield {"progress": "✅ Concluído" if result["ok"] else "❌ Falhou"}

        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _make_context(message, action, service, result)},
        ]
        yield from stream_completion(messages, self.complexity)
