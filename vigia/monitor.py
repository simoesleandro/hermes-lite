import subprocess
import urllib.request

SERVICES = {
    "hermes_lite": {
        "url": "http://localhost:5050/",
        "name": "Hermes Lite",
        "emoji": "🤖",
    },
    "syshealth": {
        "url": "http://localhost:5060/health",
        "name": "SysHealth API",
        "emoji": "💚",
    },
    "ollama": {
        "url": "http://localhost:11434/api/tags",
        "name": "Ollama",
        "emoji": "🦙",
    },
    "cronos": {
        "service_name": "HermesCronos",
        "name": "Hermes Cronos",
        "emoji": "⏰",
    },
}


def check_http(url: str, timeout: int = 5) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HermesVigia/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def check_windows_service(service_name: str) -> bool:
    try:
        result = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "RUNNING" in result.stdout
    except Exception:
        return False


def check_all() -> dict:
    status = {}
    for key, cfg in SERVICES.items():
        if "url" in cfg:
            status[key] = check_http(cfg["url"])
        else:
            status[key] = check_windows_service(cfg["service_name"])
    return status
