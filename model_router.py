import json
import os
import urllib.request
from enum import Enum

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    HEAVY  = "heavy"


# ── Providers ────────────────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    payload = json.dumps({
        "model": "llama3",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["message"]["content"]


def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
    return model.generate_content(prompt).text


# ── Routing table ─────────────────────────────────────────────────────────────
# Each level defines an ordered list of providers; first success wins.

_CHAIN: dict[Complexity, list] = {
    Complexity.SIMPLE: [_call_ollama, _call_groq,   _call_gemini],
    Complexity.MEDIUM: [_call_groq,   _call_gemini, _call_ollama],
    Complexity.HEAVY:  [_call_gemini, _call_groq,   _call_ollama],
}


def get_completion(prompt: str, complexity: Complexity) -> str:
    errors: list[str] = []
    for provider in _CHAIN[complexity]:
        try:
            return provider(prompt)
        except Exception as exc:
            errors.append(f"{provider.__name__}: {exc}")
    raise RuntimeError(
        f"All providers failed for complexity={complexity.value}.\n" +
        "\n".join(errors)
    )
