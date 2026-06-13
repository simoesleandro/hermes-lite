"""Health checks unificados — web, MCP, Ops."""

from __future__ import annotations

import os
import sqlite3
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from datetime import datetime, timezone


def check_groq() -> dict:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"status": "offline", "latency_ms": None}
    try:
        from groq import Groq
        t = time.time()
        Groq(api_key=api_key).models.list()
        return {"status": "online", "latency_ms": round((time.time() - t) * 1000)}
    except Exception:
        return {"status": "offline", "latency_ms": None}


def check_gemini() -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {"status": "offline", "latency_ms": None}
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        t = time.time()
        list(genai.list_models())
        return {"status": "online", "latency_ms": round((time.time() - t) * 1000)}
    except Exception:
        return {"status": "offline", "latency_ms": None}


def check_gemma() -> dict:
    model_id = os.getenv("GEMMA_MODEL", "gemma-4-4b-it")
    if not os.getenv("GEMINI_API_KEY", ""):
        return {"status": "offline", "latency_ms": None, "model": model_id}
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        t = time.time()
        genai.GenerativeModel(model_id).generate_content("ping")
        return {"status": "online", "latency_ms": round((time.time() - t) * 1000), "model": model_id}
    except Exception:
        return {"status": "offline", "latency_ms": None, "model": model_id}


def check_syshealth() -> dict:
    base = os.getenv("SYSHEALTH_URL", "http://localhost:5060").rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/health")
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        return {"status": "online", "latency_ms": round((time.monotonic() - t0) * 1000)}
    except Exception:
        return {"status": "offline", "latency_ms": None}


def check_sentinela() -> dict:
    from services.sentinela_client import SENTINELA_DB
    if not os.path.exists(SENTINELA_DB):
        return {"status": "offline", "contratos": None}
    try:
        conn = sqlite3.connect(f"file:{SENTINELA_DB}?mode=ro", uri=True)
        count = conn.execute("SELECT COUNT(*) FROM contratos").fetchone()[0]
        conn.close()
        return {"status": "online", "contratos": count}
    except Exception:
        return {"status": "offline", "contratos": None}


def _check_database() -> dict:
    try:
        from db.database import Database
        db = Database()
        with db._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "online"}
    except Exception as exc:
        return {"status": "offline", "error": str(exc)[:120]}


def _telegram_status() -> dict:
    return {
        "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "chat_id": bool(os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_ALLOWED_CHAT_IDS")),
        "bot_enabled": os.getenv("TELEGRAM_BOT_ENABLED", "1") == "1",
        "streaming": os.getenv("TELEGRAM_STREAMING", "1") == "1",
    }


def get_health(include_providers: bool = True) -> dict:
    """Snapshot de saúde: DB, Telegram, providers LLM e serviços externos."""
    hermes_db = _check_database()
    telegram = _telegram_status()
    providers: dict = {}
    services: dict = {}

    if include_providers:
        checks = {
            "groq": check_groq,
            "gemini": check_gemini,
            "gemma": check_gemma,
            "syshealth": check_syshealth,
            "sentinela": check_sentinela,
        }
        results: dict = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fn): name for name, fn in checks.items()}
            done, _ = futures_wait(futures, timeout=6)
            for future in done:
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception:
                    results[name] = {"status": "offline"}
            for future, name in futures.items():
                if name not in results:
                    results[name] = {"status": "offline"}

        providers = {k: results[k] for k in ("groq", "gemini", "gemma") if k in results}
        services = {k: results[k] for k in ("syshealth", "sentinela") if k in results}

    llm_online = any(p.get("status") == "online" for p in providers.values())
    ok = hermes_db.get("status") == "online" and (llm_online or not include_providers)

    return {
        "ok": ok,
        "hermes": {"database": hermes_db, "agents": 12},
        "telegram": telegram,
        "providers": providers,
        "services": services,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
