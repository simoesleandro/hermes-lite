import json
import os
import urllib.request

_OFFLINE_SUMMARY: dict = {
    "agua_hoje_ml":    None,
    "peso_kg":         None,
    "sono_horas":      None,
    "passos_hoje":     None,
    "treino_hoje":     None,
    "deficit_calorico": None,
    "proteina_g":      None,
    "carboidrato_g":   None,
    "hrv":             None,
    "fadiga":          None,
    "tirzepatida_hoje": False,
    "offline":         True,
}


class SysHealthClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("SYSHEALTH_URL", "http://localhost:5060")).rstrip("/")
        self._timeout = 10

    def _get(self, path: str) -> dict | list:
        req = urllib.request.Request(f"{self.base_url}{path}")
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())

    def register_agua(self, ml: int) -> dict:
        """Registra consumo de água em ml. Retorna {ok, error?}."""
        try:
            result = self._post("/api/agua", {"ml": ml})
            return {"ok": True, "data": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def register_peso(self, kg: float) -> dict:
        """Registra peso em kg."""
        try:
            result = self._post("/api/peso", {"kg": kg})
            return {"ok": True, "data": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def register_tirzepatida(self) -> dict:
        """Marca tirzepatida como tomada hoje."""
        try:
            result = self._post("/api/tirzepatida", {})
            return {"ok": True, "data": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

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

    def get_corridas(self, dias: int = 30) -> dict:
        try:
            return self._get(f"/api/corridas?dias={dias}")
        except Exception:
            return {"offline": True}
