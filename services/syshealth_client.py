"""Cliente SysHealth — Supabase (sys-health web) ou API Flask legada (:5060)."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("America/Sao_Paulo")

_OFFLINE_SUMMARY: dict = {
    "agua_hoje_ml": None,
    "peso_kg": None,
    "sono_horas": None,
    "passos_hoje": None,
    "treino_hoje": None,
    "deficit_calorico": None,
    "proteina_g": None,
    "carboidrato_g": None,
    "hrv": None,
    "fadiga": None,
    "tirzepatida_hoje": False,
    "offline": True,
}


def _backend_name() -> str:
    return os.getenv("SYSHEALTH_BACKEND", "supabase").strip().lower()


def _rest_url() -> str:
    explicit = (
        os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or os.getenv("SUPABASE_REST_URL")
        or ""
    ).strip().rstrip("/")
    if explicit.startswith("http"):
        return explicit
    pg = os.getenv("SUPABASE_URL", "").strip()
    match = re.search(r"postgres(?:ql)?://postgres\.([a-z0-9]+)", pg)
    if match:
        return f"https://{match.group(1)}.supabase.co"
    return ""


def _brt_day_bounds() -> tuple[str, str]:
    # PostgREST não reconhece sufixo Z em filtros — usa date-only (YYYY-MM-DD).
    # Funciona tanto para registros antigos (00:00 UTC) quanto novos (03:00+00:00).
    today = datetime.now(_TZ).date()
    tomorrow = today + timedelta(days=1)
    return today.isoformat(), tomorrow.isoformat()


class _LegacyHttpBackend:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
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
        try:
            result = self._post("/api/agua", {"ml": ml})
            return {"ok": True, "data": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def register_peso(self, kg: float) -> dict:
        try:
            result = self._post("/api/peso", {"kg": kg})
            return {"ok": True, "data": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def register_tirzepatida(self) -> dict:
        try:
            result = self._post("/api/tirzepatida", {})
            return {"ok": True, "data": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_health_summary(self) -> dict:
        try:
            return self._get("/api/resumo")
        except Exception:
            return dict(_OFFLINE_SUMMARY)

    def get_treinos_recentes(self, dias: int = 7) -> list:
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


class _SupabaseBackend:
    def __init__(self):
        self.rest_url = _rest_url()
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        self.user_id = os.getenv("SYSHEALTH_USER_ID", "").strip()
        self._timeout = 12

    def configured(self) -> bool:
        return bool(self.rest_url and self.key)

    def _headers(self, prefer: str = "return=representation") -> dict:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: list | dict | None = None,
    ) -> list | dict:
        if not self.configured():
            raise ValueError("Supabase nao configurado (URL + SUPABASE_SERVICE_ROLE_KEY)")
        qs = f"?{urllib.parse.urlencode(params)}" if params else ""
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.rest_url}{path}{qs}",
            data=data,
            headers=self._headers(),
            method=method,
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            raw = resp.read()
            if not raw:
                return []
            return json.loads(raw)

    def _query(self, table: str, *, select: str, filters: list[tuple[str, str]], order: str = "", limit: str = "") -> list:
        params: list[tuple[str, str]] = [("select", select)]
        if self.user_id:
            params.append(("user_id", f"eq.{self.user_id}"))
        params.extend(filters)
        if order:
            params.append(("order", order))
        if limit:
            params.append(("limit", limit))
        qs = urllib.parse.urlencode(params)
        data = self._request("GET", f"/rest/v1/{table}?{qs}")
        return data if isinstance(data, list) else []

    def register_agua(self, ml: int) -> dict:
        row = {
            "quantidade_ml": int(ml),
            "data_hora": datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        }
        if self.user_id:
            row["user_id"] = self.user_id
        try:
            data = self._request("POST", "/rest/v1/agua", body=[row])
            return {"ok": True, "data": data}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def register_peso(self, kg: float) -> dict:
        brt_date = datetime.now(_TZ).date().isoformat()
        payload = {"peso": float(kg)}
        try:
            existing = self._query(
                "medidas",
                select="id",
                filters=[("data", f"eq.{brt_date}")],
                limit="1",
            )
            if existing:
                row_id = existing[0]["id"]
                data = self._request(
                    "PATCH",
                    f"/rest/v1/medidas?id=eq.{row_id}",
                    body=payload,
                )
            else:
                insert = {"data": brt_date, **payload}
                if self.user_id:
                    insert["user_id"] = self.user_id
                data = self._request("POST", "/rest/v1/medidas", body=[insert])
            return {"ok": True, "data": data}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def register_tirzepatida(self) -> dict:
        return {
            "ok": False,
            "error": (
                "Tirzepatida nao esta na API Hermes — registre em sys-health "
                "(Suplementacao) ou use SYSHEALTH_BACKEND=legacy com api_server.py"
            ),
        }

    def get_health_summary(self) -> dict:
        if not self.configured():
            return dict(_OFFLINE_SUMMARY)

        result = {k: v for k, v in _OFFLINE_SUMMARY.items() if k != "offline"}
        result["offline"] = False
        result["tirzepatida_hoje"] = False

        start, end = _brt_day_bounds()

        try:
            agua_rows = self._query(
                "agua",
                select="quantidade_ml",
                filters=[("and", f"(data_hora.gte.{start},data_hora.lt.{end})")],
            )
            result["agua_hoje_ml"] = sum(int(r.get("quantidade_ml") or 0) for r in agua_rows)
        except Exception:
            pass

        try:
            medidas = self._query(
                "medidas",
                select="peso,data",
                filters=[],
                order="data.desc,id.desc",
                limit="1",
            )
            if medidas and medidas[0].get("peso") is not None:
                result["peso_kg"] = float(medidas[0]["peso"])
        except Exception:
            pass

        calorias_gastas = None
        try:
            wear = self._query(
                "amazfit_dados",
                select="sono_total_min,passos,hrv_ms,calorias_gastas",
                filters=[("and", f"(data_hora.gte.{start},data_hora.lt.{end})")],
                limit="1",
            )
            if wear:
                row = wear[0]
                sono_min = row.get("sono_total_min")
                if sono_min:
                    result["sono_horas"] = round(float(sono_min) / 60.0, 1)
                if row.get("passos") is not None:
                    result["passos_hoje"] = int(row["passos"])
                if row.get("hrv_ms") is not None:
                    result["hrv"] = int(row["hrv_ms"])
                if row.get("calorias_gastas") is not None:
                    calorias_gastas = float(row["calorias_gastas"])
        except Exception:
            pass

        try:
            treinos = self._query(
                "hevy_treinos",
                select="titulo",
                filters=[("and", f"(data_hora.gte.{start},data_hora.lt.{end})")],
                order="data_hora.desc",
                limit="1",
            )
            if treinos:
                result["treino_hoje"] = treinos[0].get("titulo")
        except Exception:
            pass

        try:
            refeicoes = self._query(
                "refeicoes",
                select="calorias,proteinas,carboidratos",
                filters=[("and", f"(data_hora.gte.{start},data_hora.lt.{end})")],
            )
            if refeicoes:
                prot = sum(float(r.get("proteinas") or 0) for r in refeicoes)
                carb = sum(float(r.get("carboidratos") or 0) for r in refeicoes)
                cal = sum(float(r.get("calorias") or 0) for r in refeicoes)
                result["proteina_g"] = round(prot, 1)
                result["carboidrato_g"] = round(carb, 1)
                if calorias_gastas is not None:
                    result["deficit_calorico"] = int(calorias_gastas - cal)
        except Exception:
            pass

        return result

    def get_treinos_recentes(self, dias: int = 7) -> list:
        if not self.configured():
            return []
        cutoff = (datetime.now(_TZ).date() - timedelta(days=dias)).isoformat()
        try:
            rows = self._query(
                "hevy_treinos",
                select="data_hora,titulo,duracao_min,volume_kg",
                filters=[("data_hora", f"gte.{cutoff}T00:00:00Z")],
                order="data_hora.desc",
            )
            return [
                {
                    "data": str(r.get("data_hora", "")),
                    "titulo": r.get("titulo"),
                    "duracao_min": r.get("duracao_min"),
                    "volume_kg": r.get("volume_kg"),
                }
                for r in rows
            ]
        except Exception:
            return []

    def get_analise_treinos(self, dias: int = 30) -> dict:
        treinos = self.get_treinos_recentes(dias)
        if not treinos:
            return {"offline": True}
        return {"total": len(treinos), "dias": dias, "treinos": treinos}

    def get_corpo(self, dias: int = 90) -> dict:
        if not self.configured():
            return {"offline": True}
        cutoff = (datetime.now(_TZ).date() - timedelta(days=dias)).isoformat()
        try:
            rows = self._query(
                "medidas",
                select="data,peso,cintura,abdomen",
                filters=[("data", f"gte.{cutoff}")],
                order="data.asc",
            )
            return {"pontos": rows}
        except Exception:
            return {"offline": True}

    def get_sono(self, dias: int = 14) -> dict:
        if not self.configured():
            return {"offline": True}
        cutoff = (datetime.now(_TZ).date() - timedelta(days=dias)).isoformat()
        try:
            rows = self._query(
                "amazfit_dados",
                select="data_hora,sono_total_min,hrv_ms",
                filters=[("data_hora", f"gte.{cutoff}T00:00:00Z")],
                order="data_hora.desc",
            )
            return {"noites": rows}
        except Exception:
            return {"offline": True}

    def get_corridas(self, dias: int = 30) -> dict:
        if not self.configured():
            return {"offline": True}
        cutoff = (datetime.now(_TZ).date() - timedelta(days=dias)).isoformat()
        try:
            rows = self._query(
                "amazfit_workouts",
                select="data_hora,distancia_km,duracao_min,pace",
                filters=[("data_hora", f"gte.{cutoff}T00:00:00Z")],
                order="data_hora.desc",
            )
            return {"corridas": rows}
        except Exception:
            return {"offline": True}


class SysHealthClient:
    """Facade — delega para Supabase (sys-health) ou HTTP legado."""

    def __init__(self, base_url: str | None = None):
        backend = _backend_name()
        if backend == "legacy":
            url = (base_url or os.getenv("SYSHEALTH_URL", "http://localhost:5060")).rstrip("/")
            self._impl = _LegacyHttpBackend(url)
            self.backend = "legacy"
        else:
            self._impl = _SupabaseBackend()
            self.backend = "supabase"

    def register_agua(self, ml: int) -> dict:
        return self._impl.register_agua(ml)

    def register_peso(self, kg: float) -> dict:
        return self._impl.register_peso(kg)

    def register_tirzepatida(self) -> dict:
        return self._impl.register_tirzepatida()

    def get_health_summary(self) -> dict:
        return self._impl.get_health_summary()

    def get_treinos_recentes(self, dias: int = 7) -> list:
        return self._impl.get_treinos_recentes(dias)

    def get_analise_treinos(self, dias: int = 30) -> dict:
        return self._impl.get_analise_treinos(dias)

    def get_corpo(self, dias: int = 90) -> dict:
        return self._impl.get_corpo(dias)

    def get_sono(self, dias: int = 14) -> dict:
        return self._impl.get_sono(dias)

    def get_corridas(self, dias: int = 30) -> dict:
        return self._impl.get_corridas(dias)


def check_syshealth_service() -> dict:
    """Health check usado pelo painel Ops — Supabase ou Flask legado."""
    backend = _backend_name()
    if backend == "legacy":
        base = os.getenv("SYSHEALTH_URL", "http://localhost:5060").rstrip("/")
        try:
            import time
            t = time.time()
            req = urllib.request.Request(f"{base}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            return {
                "status": "online",
                "latency_ms": round((time.time() - t) * 1000),
                "backend": "legacy",
                "url": base,
            }
        except Exception as exc:
            return {
                "status": "offline",
                "latency_ms": None,
                "backend": "legacy",
                "url": base,
                "error": str(exc)[:120],
            }

    sb = _SupabaseBackend()
    web = os.getenv("SYSHEALTH_WEB_URL", "http://localhost:3535").rstrip("/")
    if not sb.configured():
        return {
            "status": "offline",
            "latency_ms": None,
            "backend": "supabase",
            "error": "Defina NEXT_PUBLIC_SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY",
        }
    try:
        import time
        t = time.time()
        sb._query("medidas", select="id", filters=[], limit="1")
        out = {
            "status": "online",
            "latency_ms": round((time.time() - t) * 1000),
            "backend": "supabase",
            "project": sb.rest_url,
        }
        try:
            req = urllib.request.Request(f"{web}/")
            with urllib.request.urlopen(req, timeout=3) as resp:
                resp.read()
            out["web"] = web
        except Exception:
            out["web_offline"] = web
        return out
    except Exception as exc:
        return {
            "status": "offline",
            "latency_ms": None,
            "backend": "supabase",
            "project": sb.rest_url,
            "error": str(exc)[:120],
        }
