"""
Sincroniza resumo diário do Amazfit (Zepp Cloud) → tabela amazfit_dados no Supabase.

Uso:
    python scripts/zepp_sync.py           # últimos 2 dias
    python scripts/zepp_sync.py --days 7  # últimos 7 dias
"""

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os  # noqa: E402  (after load_dotenv)

_TZ = ZoneInfo("America/Sao_Paulo")
_ZEPP_BASE = "https://api-mifit-us3.zepp.com"
_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zepp_headers(token: str) -> dict:
    return {
        "Accept": "*/*",
        "apptoken": token,
        "appname": "com.huami.midong",
        "appplatform": "ios_phone",
        "channel": "appstore",
        "country": "BR",
        "lang": "pt_BR",
        "timezone": "America/Sao_Paulo",
        "User-Agent": "Zepp/10.3.1 (iPhone; iOS 26.4.2; Scale/3.00)",
        "v": "2.0",
    }


def _get(url: str, headers: dict) -> dict | list:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


def _decode_summary(b64: str) -> dict:
    pad = b64 + "=" * ((4 - len(b64) % 4) % 4)
    return json.loads(base64.b64decode(pad).decode("utf-8"))


def _brt_day_bounds_ms(day_str: str) -> tuple[int, int]:
    """Retorna (start_ms, end_ms) UTC dos limites do dia civil em BRT."""
    from datetime import datetime
    start = datetime.fromisoformat(f"{day_str}T00:00:00").replace(tzinfo=_TZ)
    end = datetime.fromisoformat(f"{day_str}T23:59:59.999").replace(tzinfo=_TZ)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


# ---------------------------------------------------------------------------
# Zepp API fetchers
# ---------------------------------------------------------------------------

def fetch_band_summary(day_str: str, token: str, user_id: str) -> dict | None:
    """Retorna o dict decodificado do resumo do dia, ou None se sem dados."""
    params = urllib.parse.urlencode({
        "query_type": "summary",
        "device_type": "0",
        "object_id": user_id,
        "from_date": day_str,
        "to_date": day_str,
    })
    url = f"{_ZEPP_BASE}/v1/data/band_data.json?{params}"
    payload = _get(url, _zepp_headers(token))

    code = payload.get("code")
    if code not in (None, 1, "1", 0, "0"):
        raise RuntimeError(f"Zepp code={code}: {payload.get('message', 'erro')}")

    items = payload.get("data") or []
    if not items or not items[0].get("summary"):
        return None

    return _decode_summary(items[0]["summary"])


def fetch_hrv_ms(day_str: str, token: str, user_id: str) -> int | None:
    """Extrai HRV (ms) do evento 'readiness' do dia."""
    start_ms, end_ms = _brt_day_bounds_ms(day_str)
    # lookback de 7 dias para capturar medições atrasadas
    lookback_ms = start_ms - 7 * 24 * 60 * 60 * 1000
    params = urllib.parse.urlencode({
        "eventType": "readiness",
        "from": lookback_ms,
        "to": end_ms,
        "limit": "30",
        "timeZone": "America/Sao_Paulo",
    })
    url = f"{_ZEPP_BASE}/users/{user_id}/events?{params}"
    payload = _get(url, _zepp_headers(token))
    items = payload.get("items") or []

    best_hrv = None
    best_updated = 0
    for item in items:
        if item.get("subType") == "watch_score_data":
            continue
        hrv_raw = item.get("sleepHRV")
        if hrv_raw is None or hrv_raw == "":
            continue
        hrv = float(hrv_raw)
        if hrv <= 0:
            continue
        updated = int(item.get("timestampUpdate") or item.get("timestamp") or 0)
        if updated > best_updated:
            best_updated = updated
            best_hrv = round(hrv)

    return best_hrv


def fetch_pai(day_str: str, token: str, user_id: str) -> int | None:
    """Extrai PAI total do evento 'PaiHealthInfo' do dia."""
    start_ms, end_ms = _brt_day_bounds_ms(day_str)
    params = urllib.parse.urlencode({
        "eventType": "PaiHealthInfo",
        "from": start_ms,
        "to": end_ms,
        "limit": "20",
        "timeZone": "America/Sao_Paulo",
    })
    url = f"{_ZEPP_BASE}/users/{user_id}/events?{params}"
    payload = _get(url, _zepp_headers(token))
    items = payload.get("items") or []

    best_pai = None
    best_updated = 0
    for item in items:
        pai_raw = item.get("totalPai")
        if pai_raw is None or pai_raw == "":
            continue
        pai = float(pai_raw)
        if pai <= 0:
            continue
        updated = int(item.get("uploadTimestamp") or item.get("timestamp") or 0)
        if updated >= best_updated:
            best_updated = updated
            best_pai = round(pai)

    return best_pai


# ---------------------------------------------------------------------------
# Supabase upsert
# ---------------------------------------------------------------------------

def _supabase_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def upsert_amazfit_dados(row: dict, rest_url: str, key: str) -> None:
    url = f"{rest_url}/rest/v1/amazfit_dados?on_conflict=data_hora"
    body = json.dumps([row]).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers=_supabase_headers(key),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        resp.read()


# ---------------------------------------------------------------------------
# Per-day sync
# ---------------------------------------------------------------------------

def sync_day(day_str: str, token: str, user_id: str, rest_url: str, sb_key: str, sb_user_id: str) -> bool:
    """Processa um dia. Retorna True em sucesso."""
    try:
        summary = fetch_band_summary(day_str, token, user_id)
        if summary is None:
            print(f"  [{day_str}] sem dados na API Zepp — pulando")
            return True

        stp = summary.get("stp") or {}
        slp = summary.get("slp") or {}

        deep = int(slp.get("dp") or 0)
        light = int(slp.get("lt") or 0)
        rem = int(slp.get("dt") or 0)
        sono_total = deep + light + rem or int(slp.get("ebt") or 0)

        run_dist_m = float(stp.get("runDist") or 0)

        # Meia-noite BRT em UTC = 03:00:00Z (BRT = UTC-3)
        row: dict = {
            "data_hora": f"{day_str}T03:00:00+00:00",
            "passos": int(stp.get("ttl") or 0),
            "calorias_gastas": int(stp.get("cal") or 0),
            "distancia_km": round(float(stp.get("dis") or 0) / 1000, 2),
            "sono_total_min": sono_total,
            "sono_profundo_min": deep,
            "corrida_km": round(run_dist_m / 1000, 2),
            "corrida_cal": int(stp.get("runCal") or 0),
            "hrv_ms": 0,
            "pai": 0,
        }
        if sb_user_id:
            row["user_id"] = sb_user_id

        # HRV e PAI — falha silenciosa para não bloquear o resumo
        try:
            hrv = fetch_hrv_ms(day_str, token, user_id)
            if hrv is not None:
                row["hrv_ms"] = hrv
        except Exception as exc:
            print(f"  [{day_str}] aviso HRV: {exc}")

        try:
            pai = fetch_pai(day_str, token, user_id)
            if pai is not None:
                row["pai"] = pai
        except Exception as exc:
            print(f"  [{day_str}] aviso PAI: {exc}")

        upsert_amazfit_dados(row, rest_url, sb_key)

        print(
            f"  [{day_str}] OK — "
            f"passos={row['passos']} cal={row['calorias_gastas']} "
            f"sono={row['sono_total_min']}min hrv={row['hrv_ms']}ms pai={row['pai']} "
            f"corrida={row['corrida_km']}km"
        )
        return True

    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            print(f"  [{day_str}] ERRO 401 — token Zepp inválido ou expirado. Atualize ZEPP_APP_TOKEN.")
        else:
            print(f"  [{day_str}] ERRO HTTP {exc.code}: {exc.reason}")
        return False
    except Exception as exc:
        print(f"  [{day_str}] ERRO: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _resolve_rest_url() -> str:
    explicit = (
        os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or os.getenv("SUPABASE_REST_URL")
        or ""
    ).strip().rstrip("/")
    if explicit.startswith("http"):
        return explicit
    import re
    pg = os.getenv("SUPABASE_URL", "").strip()
    match = re.search(r"postgres(?:ql)?://postgres\.([a-z0-9]+)", pg)
    if match:
        return f"https://{match.group(1)}.supabase.co"
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Zepp → Supabase amazfit_dados")
    parser.add_argument("--days", type=int, default=2, help="Quantos dias retroativos buscar (padrão: 2)")
    args = parser.parse_args()

    token = os.getenv("ZEPP_APP_TOKEN", "").strip()
    user_id = os.getenv("ZEPP_USER_ID", "").strip()
    rest_url = _resolve_rest_url()
    sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    sb_user_id = os.getenv("SYSHEALTH_USER_ID", "").strip()

    errors = []
    if not token:
        errors.append("ZEPP_APP_TOKEN não configurado")
    if not user_id:
        errors.append("ZEPP_USER_ID não configurado")
    if not rest_url:
        errors.append("NEXT_PUBLIC_SUPABASE_URL não configurado")
    if not sb_key:
        errors.append("SUPABASE_SERVICE_ROLE_KEY não configurado")
    if errors:
        for e in errors:
            print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    days_to_sync = [
        (today - timedelta(days=i)).isoformat()
        for i in range(args.days - 1, -1, -1)
    ]

    print(f"Zepp Sync - {args.days} dia(s): {days_to_sync[0]} -> {days_to_sync[-1]}")

    ok = 0
    fail = 0
    for day_str in days_to_sync:
        if sync_day(day_str, token, user_id, rest_url, sb_key, sb_user_id):
            ok += 1
        else:
            fail += 1

    print(f"\nConcluído: {ok} OK, {fail} falha(s)")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
