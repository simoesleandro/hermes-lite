"""Health checks unificados — web, MCP, Ops."""

from __future__ import annotations

import json
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


def _gemma_model_ids() -> set[str]:
    """IDs Gemma disponíveis na Gemini API (com e sem prefixo models/)."""
    if not os.getenv("GEMINI_API_KEY", ""):
        return set()
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        ids: set[str] = set()
        for m in genai.list_models():
            if "gemma" not in m.name.lower():
                continue
            ids.add(m.name)
            ids.add(m.name.split("/")[-1])
        return ids
    except Exception:
        return set()


def _ollama_model_names() -> set[str]:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        names: set[str] = set()
        for m in data.get("models", []):
            name = m.get("name", "")
            if name:
                names.add(name)
                names.add(name.split(":")[0])
        return names
    except Exception:
        return set()


def check_gemma() -> dict:
    provider = os.getenv("GEMMA_PROVIDER", "ollama").strip().lower()
    if provider == "ollama":
        model = os.getenv("OLLAMA_GEMMA_MODEL", "gemma4:12b").strip()
        available = _ollama_model_names()
        if not available:
            return {
                "status": "offline",
                "latency_ms": None,
                "model": model,
                "provider": "ollama",
                "error": "Ollama nao responde em OLLAMA_BASE_URL",
            }
        if model not in available and model.split(":")[0] not in available:
            return {
                "status": "offline",
                "latency_ms": None,
                "model": model,
                "provider": "ollama",
                "error": f"modelo nao instalado — rode: ollama pull {model}",
            }
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        try:
            t = time.time()
            req = urllib.request.Request(f"{base}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            return {
                "status": "online",
                "latency_ms": round((time.time() - t) * 1000),
                "model": model,
                "provider": "ollama",
            }
        except Exception as exc:
            return {
                "status": "offline",
                "latency_ms": None,
                "model": model,
                "provider": "ollama",
                "error": str(exc)[:120],
            }

    model_id = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it").strip()
    bare = model_id.replace("models/", "")
    if not os.getenv("GEMINI_API_KEY", ""):
        return {"status": "offline", "latency_ms": None, "model": bare, "provider": "gemini"}

    available = _gemma_model_ids()
    if available and bare not in available and f"models/{bare}" not in available:
        hint = "gemma-4-12b-it ainda nao esta na Gemini API; use gemma-4-26b-a4b-it"
        if "12" in bare:
            return {
                "status": "offline",
                "latency_ms": None,
                "model": bare,
                "error": hint,
            }
        return {
            "status": "offline",
            "latency_ms": None,
            "model": bare,
            "error": f"modelo nao listado na API: {bare}",
        }

    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        t = time.time()
        # count_tokens e rapido (~300ms); generate_content estourava timeout de 6s
        genai.GenerativeModel(bare).count_tokens("ping")
        return {
            "status": "online",
            "latency_ms": round((time.time() - t) * 1000),
            "model": bare,
            "provider": "gemini",
        }
    except Exception as exc:
        return {
            "status": "offline",
            "latency_ms": None,
            "model": bare,
            "provider": "gemini",
            "error": str(exc)[:120],
        }


def check_syshealth() -> dict:
    from services.syshealth_client import check_syshealth_service
    return check_syshealth_service()


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
            done, _ = futures_wait(futures, timeout=15)
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
