import json
import logging
import os
import time
import urllib.request
from enum import Enum
from typing import Generator

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("hermes.model_router")

GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMMA_PROVIDER    = os.getenv("GEMMA_PROVIDER", "ollama").strip().lower()
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_GEMMA_MODEL = os.getenv("OLLAMA_GEMMA_MODEL", "gemma4:12b")
GEMMA_MODEL       = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")


def _gemma_model_label() -> str:
    if GEMMA_PROVIDER == "ollama":
        return OLLAMA_GEMMA_MODEL
    return GEMMA_MODEL

_METRICS: list[dict] = []
_METRICS_MAX = 500


class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    HEAVY  = "heavy"


# ── Message normalisation helpers ────────────────────────────────────────────

def _text_only_messages(messages: list[dict]) -> list[dict]:
    """Flatten multipart content to plain text for non-vision providers."""
    result = []
    for m in messages:
        content = m["content"]
        if isinstance(content, list):
            texts = [p["text"] for p in content if p.get("type") == "text"]
            if any(p.get("type") == "image" for p in content):
                texts.append("[Nota: imagem anexada não suportada por este modelo]")
            result.append({"role": m["role"], "content": " ".join(texts)})
        else:
            result.append(m)
    return result


def _build_gemini_contents(messages: list[dict]) -> list[dict]:
    """Convert messages to Gemini contents format with vision support."""
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        content = m["content"]
        if isinstance(content, str):
            parts = [{"text": content}]
        else:
            parts = []
            for p in content:
                if p.get("type") == "text":
                    parts.append({"text": p["text"]})
                elif p.get("type") == "image":
                    parts.append({"inline_data": {"mime_type": p["mime_type"], "data": p["data"]}})
        contents.append({"role": role, "parts": parts})
    return contents


# ── Ollama (Gemma 4 local) ───────────────────────────────────────────────────

def _ollama_messages(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        content = m["content"]
        if isinstance(content, list):
            texts = [p["text"] for p in content if p.get("type") == "text"]
            if any(p.get("type") == "image" for p in content):
                texts.append("[Nota: imagem anexada nao suportada pelo Gemma local]")
            content = " ".join(texts)
        out.append({"role": m["role"], "content": content})
    return out


def _ollama_post(path: str, payload: dict, timeout: float = 300) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _call_ollama(messages: list[dict]) -> str:
    body = _ollama_post(
        "/api/chat",
        {
            "model": OLLAMA_GEMMA_MODEL,
            "messages": _ollama_messages(messages),
            "stream": False,
        },
    )
    return body["message"]["content"]


def _stream_ollama(messages: list[dict]) -> Generator[str, None, None]:
    data = json.dumps(
        {
            "model": OLLAMA_GEMMA_MODEL,
            "messages": _ollama_messages(messages),
            "stream": True,
        }
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("message", {}).get("content")
            if token:
                yield token


# ── Google (Gemini + Gemma 4 via Gemini API) ─────────────────────────────────

def _call_google(model: str, messages: list[dict]) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    system_content = next((m["content"] for m in messages if m["role"] == "system"), None)
    contents = _build_gemini_contents(messages)
    gmodel = genai.GenerativeModel(model, system_instruction=system_content)
    return gmodel.generate_content(contents).text


def _stream_google(model: str, messages: list[dict]) -> Generator[str, None, None]:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    system_content = next((m["content"] for m in messages if m["role"] == "system"), None)
    contents = _build_gemini_contents(messages)
    gmodel = genai.GenerativeModel(model, system_instruction=system_content)
    for chunk in gmodel.generate_content(contents, stream=True):
        token = chunk.text
        if token:
            yield token


def _call_gemma(messages: list[dict]) -> str:
    if GEMMA_PROVIDER == "ollama":
        return _call_ollama(messages)
    return _call_google(GEMMA_MODEL, messages)


def _call_gemini(messages: list[dict]) -> str:
    return _call_google(GEMINI_MODEL, messages)


def _stream_gemma(messages: list[dict]) -> Generator[str, None, None]:
    if GEMMA_PROVIDER == "ollama":
        yield from _stream_ollama(messages)
        return
    yield from _stream_google(GEMMA_MODEL, messages)


def _stream_gemini(messages: list[dict]) -> Generator[str, None, None]:
    yield from _stream_google(GEMINI_MODEL, messages)


# ── Groq ──────────────────────────────────────────────────────────────────────

def _call_groq(messages: list[dict]) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=_text_only_messages(messages),
    )
    return resp.choices[0].message.content


def _stream_groq(messages: list[dict]) -> Generator[str, None, None]:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=_text_only_messages(messages),
        stream=True,
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


# ── Routing tables ────────────────────────────────────────────────────────────

_CHAIN: dict[Complexity, list] = {
    Complexity.SIMPLE: [_call_gemma,  _call_groq,   _call_gemini],
    Complexity.MEDIUM: [_call_groq,   _call_gemini, _call_gemma],
    Complexity.HEAVY:  [_call_gemini, _call_groq,   _call_gemma],
}

_STREAM_CHAIN: dict[Complexity, list] = {
    Complexity.SIMPLE: [_stream_gemma,  _stream_groq,   _stream_gemini],
    Complexity.MEDIUM: [_stream_groq,   _stream_gemini, _stream_gemma],
    Complexity.HEAVY:  [_stream_gemini, _stream_groq,   _stream_gemma],
}


# ── Public API ────────────────────────────────────────────────────────────────

def _record_metric(provider: str, complexity: Complexity, latency_ms: float, fallback: bool) -> None:
    entry = {
        "provider": provider,
        "complexity": complexity.value,
        "latency_ms": round(latency_ms, 1),
        "fallback": fallback,
        "ts": time.time(),
    }
    _METRICS.append(entry)
    if len(_METRICS) > _METRICS_MAX:
        del _METRICS[: len(_METRICS) - _METRICS_MAX]
    logger.info(
        "completion provider=%s complexity=%s latency_ms=%s fallback=%s",
        provider, complexity.value, entry["latency_ms"], fallback,
    )


def get_metrics() -> dict:
    cutoff = time.time() - 86400
    recent = [m for m in _METRICS if m["ts"] >= cutoff]
    by_provider: dict[str, int] = {}
    by_complexity: dict[str, int] = {}
    latency_sum: dict[str, float] = {}
    latency_count: dict[str, int] = {}
    for m in recent:
        p = m["provider"]
        by_provider[p] = by_provider.get(p, 0) + 1
        c = m["complexity"]
        by_complexity[c] = by_complexity.get(c, 0) + 1
        latency_sum[p] = latency_sum.get(p, 0) + m["latency_ms"]
        latency_count[p] = latency_count.get(p, 0) + 1
    avg_latency = {
        p: round(latency_sum[p] / latency_count[p], 1)
        for p in latency_sum
    }
    return {
        "total_24h": len(recent),
        "by_provider": by_provider,
        "by_complexity": by_complexity,
        "avg_latency_ms": avg_latency,
        "recent": recent[-20:],
        "models": {
            "gemma": _gemma_model_label(),
            "gemma_provider": GEMMA_PROVIDER,
            "gemini": GEMINI_MODEL,
        },
    }


def get_completion(messages: list[dict], complexity: Complexity) -> str:
    errors: list[str] = []
    for i, provider in enumerate(_CHAIN[complexity]):
        name = provider.__name__.replace("_call_", "")
        t0 = time.time()
        try:
            result = provider(messages)
            _record_metric(name, complexity, (time.time() - t0) * 1000, fallback=i > 0)
            return result
        except Exception as exc:
            errors.append(f"{provider.__name__}: {exc}")
    raise RuntimeError(
        f"All providers failed for complexity={complexity.value}.\n" +
        "\n".join(errors)
    )


def stream_completion(messages: list[dict], complexity: Complexity) -> Generator:
    """Yields string tokens followed by a final dict {"provider": name}."""
    errors: list[str] = []
    for i, provider_fn in enumerate(_STREAM_CHAIN[complexity]):
        provider_name = provider_fn.__name__.replace("_stream_", "")
        t0 = time.time()
        try:
            gen = provider_fn(messages)
            first = next(gen)
        except StopIteration:
            _record_metric(provider_name, complexity, (time.time() - t0) * 1000, fallback=i > 0)
            yield {"provider": provider_name}
            return
        except Exception as exc:
            errors.append(f"{provider_fn.__name__}: {exc}")
            continue
        _record_metric(provider_name, complexity, (time.time() - t0) * 1000, fallback=i > 0)
        yield first
        yield from gen
        yield {"provider": provider_name}
        return
    raise RuntimeError(
        f"All streaming providers failed for complexity={complexity.value}.\n" +
        "\n".join(errors)
    )
