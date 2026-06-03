import json
import urllib.request
from urllib.error import URLError

_OFFLINE_SUMMARY: dict = {
    "agua":        None,
    "peso":        None,
    "sono":        None,
    "passos":      None,
    "treino":      None,
    "deficit":     None,
    "proteina":    None,
    "tirzepatida": None,
    "offline":     True,
}


class SysHealthClient:
    def __init__(self, base_url: str = "http://localhost:5060"):
        self.base_url = base_url.rstrip("/")
        self._timeout = 3

    def _get(self, path: str) -> dict | list:
        req = urllib.request.Request(f"{self.base_url}{path}")
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())

    def get_health_summary(self) -> dict:
        """Retorna resumo diário do SysHealth. Offline → dict com valores None."""
        try:
            return self._get("/api/resumo")
        except Exception:
            return dict(_OFFLINE_SUMMARY)

    def get_treinos_recentes(self, dias: int = 7) -> list:
        """Retorna treinos dos últimos N dias. Offline → lista vazia."""
        try:
            return self._get(f"/api/treinos?dias={dias}")
        except Exception:
            return []

    def get_analise_treinos(self, dias: int = 30) -> dict:
        try:
            return self._get(f"/api/treinos/analise?dias={dias}")
        except Exception:
            return {"offline": True}

    def get_corpo(self, dias: int = 90) -> dict:
        try:
            return self._get(f"/api/corpo?dias={dias}")
        except Exception:
            return {"offline": True}

    def get_sono(self, dias: int = 14) -> dict:
        try:
            return self._get(f"/api/sono?dias={dias}")
        except Exception:
            return {"offline": True}
