import re
import subprocess
import time
from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion

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
    r'\b(status|estado|online|offline|rodando|ativo|parado|funcionando|'
    r'qual\s+servi|como\s+est[áa]|verificar|checar)\b',
    re.I,
)

_SYSTEM = (
    "Você é o agente de operações do Hermes Lite. "
    "Confirme ações executadas nos serviços Windows e explique o resultado. "
    "Seja direto e objetivo. Responda em português."
)


# ── sc helpers ────────────────────────────────────────────────────────────────

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
        results.append({"service": svc, "state": state})
    return results


def _format_status(statuses: list[dict]) -> str:
    lines = ["Serviços Windows:"]
    for s in statuses:
        icon = "✅" if s["state"] == "RUNNING" else "❌"
        lines.append(f"  {icon} {s['service']} — {s['state']}")
    return "\n".join(lines)


def _format_sc_result(action: str, service: str, result: dict) -> str:
    icon = "✅" if result["ok"] else "❌"
    status = "sucesso" if result["ok"] else "falhou"
    lines = [f"{icon} sc {action} {service} — {status}"]
    if result["stdout"]:
        lines.append(result["stdout"][:400])
    if result["stderr"]:
        lines.append(f"Erro: {result['stderr'][:200]}")
    return "\n".join(lines)


# ── intent parser ─────────────────────────────────────────────────────────────

def _parse(message: str) -> tuple[str | None, str | None]:
    """Return (intent, service).

    intent values:
      "status"                     → run sc query (service may be None = all)
      "start" / "stop" / "restart" → run sc action on service
      None                         → conversational fallback
    """
    has_action = bool(_ACT_RE.search(message))
    has_status = bool(_STATUS_RE.search(message))
    sm = _SVC_RE.search(message)
    service = _SERVICES.get(sm.group(1).lower()) if sm else None

    if has_action:
        am = _ACT_RE.search(message)
        action = _ACTIONS[am.group(1).lower()]
        return action, service  # service may be None → will ask for target

    # No control verb: any mention of a service OR status keyword → status query
    if has_status or service:
        return "status", service  # service=None means show all

    return None, None


def _make_context(message: str, action: str, service: str, result: dict) -> str:
    return (
        f"Pedido: {message}\n"
        f"Comando: sc {action} {service}\n"
        f"Resultado: {'sucesso' if result['ok'] else 'falhou'}\n"
        f"Output: {result['stdout'][:400] or '(vazio)'}\n"
        f"Stderr: {result['stderr'][:200] or 'nenhum'}"
    )


# ── agent ─────────────────────────────────────────────────────────────────────

class OpsAgent(BaseAgent):
    name       = "ops"
    complexity = Complexity.SIMPLE
    system_prompt = _SYSTEM

    def __init__(self, db=None):
        super().__init__(db)

    def _build_messages(self, message: str, session_id: str) -> list[dict]:
        history = self.db.get_history_as_messages(self.name, session_id) if self.db else []
        return (
            [{"role": "system", "content": self.system_prompt}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(self, message: str, session_id: str) -> str:
        action, service = _parse(message)

        if action == "status":
            return _format_status(_query_all_status())

        if action in ("start", "stop", "restart") and service:
            return _format_sc_result(action, service, _run_sc(action, service))

        return get_completion(self._build_messages(message, session_id), self.complexity)

    def stream(self, message: str, session_id: str) -> Generator:
        action, service = _parse(message)

        if action == "status":
            yield {"progress": "🔍 Consultando status dos serviços..."}
            yield _format_status(_query_all_status())
            return

        if action in ("start", "stop", "restart") and service:
            yield {"progress": f"⚙️ Executando: sc {action} {service}..."}
            yield _format_sc_result(action, service, _run_sc(action, service))
            return

        yield from stream_completion(self._build_messages(message, session_id), self.complexity)
