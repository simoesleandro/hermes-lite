import json
import os
import urllib.request
from enum import Enum
from typing import Generator

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    HEAVY  = "heavy"


# ── Blocking providers ────────────────────────────────────────────────────────

def _call_ollama(messages: list[dict]) -> str:
    payload = json.dumps({
        "model": "llama3",
        "messages": messages,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["message"]["content"]


def _call_groq(messages: list[dict]) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
    )
    return resp.choices[0].message.content


def _call_gemini(messages: list[dict]) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)

    system_content = next((m["content"] for m in messages if m["role"] == "system"), None)
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages if m["role"] != "system"
    ]
    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_content)
    return model.generate_content(contents).text


# ── Streaming providers ───────────────────────────────────────────────────────

def _stream_ollama(messages: list[dict]) -> Generator[str, None, None]:
    payload = json.dumps({
        "model": "llama3",
        "messages": messages,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
            if chunk.get("done"):
                break


def _stream_groq(messages: list[dict]) -> Generator[str, None, None]:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


def _stream_gemini(messages: list[dict]) -> Generator[str, None, None]:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)

    system_content = next((m["content"] for m in messages if m["role"] == "system"), None)
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages if m["role"] != "system"
    ]
    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_content)
    for chunk in model.generate_content(contents, stream=True):
        token = chunk.text
        if token:
            yield token


# ── Routing tables ────────────────────────────────────────────────────────────

_CHAIN: dict[Complexity, list] = {
    Complexity.SIMPLE: [_call_ollama, _call_groq,   _call_gemini],
    Complexity.MEDIUM: [_call_groq,   _call_gemini, _call_ollama],
    Complexity.HEAVY:  [_call_gemini, _call_groq,   _call_ollama],
}

_STREAM_CHAIN: dict[Complexity, list] = {
    Complexity.SIMPLE: [_stream_ollama, _stream_groq,   _stream_gemini],
    Complexity.MEDIUM: [_stream_groq,   _stream_gemini, _stream_ollama],
    Complexity.HEAVY:  [_stream_gemini, _stream_groq,   _stream_ollama],
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_completion(messages: list[dict], complexity: Complexity) -> str:
    errors: list[str] = []
    for provider in _CHAIN[complexity]:
        try:
            return provider(messages)
        except Exception as exc:
            errors.append(f"{provider.__name__}: {exc}")
    raise RuntimeError(
        f"All providers failed for complexity={complexity.value}.\n" +
        "\n".join(errors)
    )


def stream_completion(messages: list[dict], complexity: Complexity) -> Generator[str, None, None]:
    """Yields string tokens. Tries each provider in chain; falls back if setup fails.
    Raises RuntimeError only if all providers fail before yielding anything."""
    errors: list[str] = []
    for provider_fn in _STREAM_CHAIN[complexity]:
        try:
            gen = provider_fn(messages)
            first = next(gen)   # fail-fast: raises if provider is down before first token
        except StopIteration:
            return              # provider succeeded with empty response
        except Exception as exc:
            errors.append(f"{provider_fn.__name__}: {exc}")
            continue
        # Provider is live — hand off the stream (mid-stream errors propagate to caller)
        yield first
        yield from gen
        return
    raise RuntimeError(
        f"All streaming providers failed for complexity={complexity.value}.\n" +
        "\n".join(errors)
    )
