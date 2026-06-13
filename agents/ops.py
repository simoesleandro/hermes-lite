import re
import subprocess
import time
import urllib.request
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

# nome amigável → nome real registrado no Windows
_SC_NAMES = {
    "HermesCronos":      "HermesCronos",
    "HermesVigia":       "hermes-vigia",
    "HermesSysHealthAPI": "HermesSysHealthAPI",
    "HermesLite":        "HermesLite",
}

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
    sc_name = _SC_NAMES.get(service, service)
    try:
        if action == "restart":
            r1 = subprocess.run(
                ["powershell", "-Command", f'Stop-Service -Name "{sc_name}" -Force'],
                capture_output=True, text=True, timeout=10,
            )
            time.sleep(2)
            r2 = subprocess.run(
                ["powershell", "-Command", f'Start-Service -Name "{sc_name}"'],
                capture_output=True, text=True, timeout=10,
            )
            return {
                "ok":     r2.returncode == 0,
                "stdout": f"[stop]  {r1.stdout.strip()}\n[start] {r2.stdout.strip()}",
                "stderr": " | ".join(filter(None, [r1.stderr.strip(), r2.stderr.strip()])),
            }
        ps_cmd = (
            f'Start-Service -Name "{sc_name}"' if action == "start"
            else f'Stop-Service -Name "{sc_name}" -Force'
        )
        r = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10,
        )
        return {"ok": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout após 10s"}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


def _check_syshealth_http() -> str:
    try:
        urllib.request.urlopen("http://localhost:5060/api/resumo", timeout=2)
        return "RUNNING"
    except Exception:
        return "STOPPED"


def _query_all_status() -> list[dict]:
    results = []
    for svc in _ALL_SERVICES:
        if svc == "HermesSysHealthAPI":
            state = _check_syshealth_http()
        else:
            sc_name = _SC_NAMES.get(svc, svc)
            try:
                r = subprocess.run(
                    ["powershell", "-Command", f'(Get-Service -Name "{sc_name}").Status'],
                    capture_output=True, text=True, timeout=5,
                )
                state = r.stdout.strip().upper() or ("STOPPED" if r.returncode != 0 else "UNKNOWN")
            except subprocess.TimeoutExpired:
                state = "TIMEOUT"
            except Exception as e:
                state = f"ERRO: {e}"
        results.append({"service": svc, "state": state})
    return results


def _format_status(statuses: list[dict]) -> str:
    lines = ["Serviços Windows:"]
    for s in statuses:
        state = s["state"]
        if state == "RUNNING":
            icon = "✅"
        elif state == "TIMEOUT":
            icon = "❓"
        else:
            icon = "❌"
        lines.append(f"  {icon} {s['service']} — {state}")
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

    def _build_messages(
        self, message: str, session_id: str, conversation_id: str | None = None,
    ) -> list[dict]:
        history = self._get_history(session_id, conversation_id) if self.db else []
        system = self.system_prompt + (self._memory_block(conversation_id) if self.db else "")
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(
        self, message: str, session_id: str, image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        action, service = _parse(message)

        if action == "status":
            return _format_status(_query_all_status())

        if action in ("start", "stop", "restart") and service:
            return _format_sc_result(action, service, _run_sc(action, service))

        return get_completion(
            self._build_messages(message, session_id, conversation_id), self.complexity,
        )

    def stream(
        self, message: str, session_id: str, image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> Generator:
        action, service = _parse(message)

        if action == "status":
            yield {"progress": "🔍 Consultando status dos serviços..."}
            yield _format_status(_query_all_status())
            return

        if action in ("start", "stop", "restart") and service:
            yield {"progress": f"⚙️ Executando: sc {action} {service}..."}
            yield _format_sc_result(action, service, _run_sc(action, service))
            return

        yield from stream_completion(
            self._build_messages(message, session_id, conversation_id), self.complexity,
        )
