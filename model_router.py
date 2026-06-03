"""
model_router.py — Sistema Multi-Modelo Dinâmico do Hermes Agent v2

Classifica a complexidade de cada mensagem/tarefa e retorna o LLM ideal:
  - SIMPLE  → Ollama local (hermes_llama) — custo zero, rápido
  - MEDIUM  → Gemini 2.5 Flash — rápido e barato via API
  - HEAVY   → Claude Sonnet 4 — máxima qualidade em raciocínio

Inclui fallback automático: Claude → Gemini → Ollama
"""

import os
import re
import time
import logging
from enum import Enum
from dotenv import load_dotenv
from crewai import LLM

# Carrega .env do Hermes e do Projeto_Fit (onde tem a GEMINI_API_KEY)
load_dotenv(r"c:\Users\Leand\OneDrive\Desktop\Hermes_Agent\.env")
load_dotenv(r"c:\Users\Leand\OneDrive\Desktop\Projeto_Fit\.env")

logger = logging.getLogger("model_router")


# ─── CONFIGURAÇÃO DOS MODELOS ────────────────────────────────────────────

class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    HEAVY = "heavy"


# Chaves de API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Contadores para logging/diagnóstico
_stats = {"simple": 0, "medium": 0, "heavy": 0, "fallbacks": 0}


# ─── CLASSIFICADOR DE COMPLEXIDADE ──────────────────────────────────────

# Keywords que indicam tarefas SIMPLES (ação direta, sem raciocínio complexo)
_SIMPLE_PATTERNS = [
    # Saúde — registros rápidos
    r"\b\d+\s*ml\b", r"\bbebi\b", r"\bagua\b", r"\bágua\b",
    r"\bpeso\s*:?\s*\d", r"\btirzepatida\b", r"\bmedicaçao\b", r"\bmedicacao\b",
    r"\bsync\s*hevy\b", r"\bsincronizar\s*treinos\b",
    # Comandos diretos
    r"^/\w+$",  # /ajuda, /sync_treinos, etc.
    r"^ajuda$", r"^help$",
    # Confirmações simples
    r"^sim$", r"^não$", r"^ok$", r"^pode$", r"^cancelar?$",
]

# Keywords que indicam tarefas PESADAS (planejamento, análise profunda, código)
_HEAVY_KEYWORDS = [
    # Planejamento e análise
    "planejar", "planejamento", "organizar meus estudos", "organizar estudo",
    "montar cronograma", "metas da semana", "relatório semanal",
    "resumo matinal", "análise completa", "briefing",
    # Código e arquitetura
    "blueprint", "arquitetura", "implementar", "refatorar", "código completo",
    "criar aplicativo", "criar um aplicativo", "criar app", "criar projeto", "design system",
    "modelar banco", "criar api", "endpoint",
    # Análise profunda
    "comparar", "avaliar", "prós e contras", "trade-off", "tradeoff",
    "pesquise a fundo", "pesquisa detalhada", "analise detalhada",
]

# Keywords que indicam tarefas MÉDIAS
_MEDIUM_KEYWORDS = [
    # Resumos e pesquisas
    "resumir", "resumo", "resuma", "pesquisar", "pesquise", "buscar na web",
    "o que é", "como funciona", "me explique", "explique",
    # Classificação e roteamento inteligente
    "tarefa", "adicionar tarefa", "backlog", "ideia para",
    # Obsidian e notas
    "salvar nota", "criar nota", "anotar", "nota de estudo",
]


def classify_complexity(mensagem: str) -> Complexity:
    """
    Classifica a complexidade de uma mensagem para decidir qual modelo usar.
    
    Heurística:
      1. Se a mensagem bate com padrões SIMPLE → SIMPLE
      2. Se contém keywords HEAVY → HEAVY
      3. Se contém keywords MEDIUM ou tem tamanho moderado → MEDIUM
      4. Se a mensagem é curta (< 30 chars) → SIMPLE
      5. Se a mensagem é longa (> 500 chars) → HEAVY
      6. Default → MEDIUM
    """
    texto = mensagem.lower().strip()
    
    # 1. Padrões SIMPLE (regex match)
    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, texto):
            return Complexity.SIMPLE
    
    # 2. Keywords HEAVY
    for keyword in _HEAVY_KEYWORDS:
        if keyword in texto:
            return Complexity.HEAVY
    
    # 3. Keywords MEDIUM
    for keyword in _MEDIUM_KEYWORDS:
        if keyword in texto:
            return Complexity.MEDIUM
    
    # 4. Heurística de tamanho
    if len(texto) < 30:
        return Complexity.SIMPLE
    elif len(texto) > 500:
        return Complexity.HEAVY
    
    # 5. Default
    return Complexity.MEDIUM


# ─── FÁBRICA DE LLMs ────────────────────────────────────────────────────

def _create_ollama_llm() -> LLM:
    """Cria o LLM local via Ollama."""
    return LLM(model="ollama/hermes_llama", base_url="http://localhost:11434")


def _create_gemini_llm() -> LLM:
    """Cria o LLM Gemini 2.5 Flash via API."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não configurada")
    
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    return LLM(
        model="gemini/gemini-2.5-flash",
        api_key=GEMINI_API_KEY,
        num_retries=5
    )


def _create_groq_llm() -> LLM:
    """Cria o LLM Groq llama-3.3-70b-versatile via API."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY não configurada")
    return LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=GROQ_API_KEY,
        num_retries=3,
    )


def _create_claude_llm() -> LLM:
    """Cria o LLM Claude Sonnet 4 via API."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY não configurada")
    
    return LLM(
        model="anthropic/claude-3-5-sonnet-20241022",
        api_key=ANTHROPIC_API_KEY,
    )


def _wrap_llm_call(llm: LLM, fallback_factory=None) -> LLM:
    """
    Decora o método .call do LLM para:
    1. Retentativas com backoff exponencial em erros 503/429.
    2. Fallback via fallback_factory para erros não recuperáveis durante chamadas,
       corrigindo a lacuna onde apenas erros de criação caíam no Ollama.
    """
    try:
        original_call = llm.call

        def resilient_call(*args, **kwargs):
            max_attempts = 5
            delay = 2
            for attempt in range(1, max_attempts + 1):
                try:
                    return original_call(*args, **kwargs)
                except Exception as e:
                    err_str = str(e)
                    is_transient = any(x in err_str.lower() for x in [
                        "503", "temporarily unavailable", "busy", "overloaded", "unavailable",
                        "429", "rate limit", "quota",
                    ])
                    if is_transient and attempt < max_attempts:
                        logger.warning(
                            f"⚠️ Chamada LLM falhou ({err_str[:80]}). "
                            f"Retentando em {delay}s ({attempt}/{max_attempts})..."
                        )
                        time.sleep(delay)
                        delay *= 2
                    else:
                        if fallback_factory:
                            logger.warning(
                                f"⚠️ LLM primário falhou definitivamente ({err_str[:80]}). "
                                f"Ativando fallback Ollama..."
                            )
                            _stats["fallbacks"] += 1
                            return fallback_factory().call(*args, **kwargs)
                        raise e

        llm.call = resilient_call
    except Exception as e:
        logger.warning(f"Não foi possível aplicar monkey patch de resiliência no LLM: {e}")
    return llm


def get_llm(complexity: Complexity | str = Complexity.MEDIUM) -> LLM:
    """
    Retorna o LLM adequado para a complexidade especificada.
    
    Inclui fallback automático:
      - HEAVY: Claude → Gemini → Ollama
      - MEDIUM: Gemini → Ollama
      - SIMPLE: Ollama direto
    
    Args:
        complexity: Complexity enum ou string ("simple", "medium", "heavy")
    
    Returns:
        LLM configurado e pronto para uso
    """
    if isinstance(complexity, str):
        complexity = Complexity(complexity.lower())
    
    _stats[complexity.value] += 1
    
    if complexity == Complexity.SIMPLE:
        logger.info("🟢 Modelo: Ollama local (SIMPLE)")
        return _create_ollama_llm()
    
    elif complexity == Complexity.MEDIUM:
        # Tenta Groq → fallback Gemini → fallback Ollama
        try:
            llm = _create_groq_llm()
            logger.info("🟡 Modelo: Groq llama-3.3-70b-versatile (MEDIUM)")
            return _wrap_llm_call(llm, fallback_factory=_create_ollama_llm)
        except Exception as e:
            logger.warning(f"⚠️ Groq indisponível ({e}), tentando Gemini...")
        try:
            llm = _create_gemini_llm()
            logger.info("🟡 Modelo: Gemini 2.5 Flash (MEDIUM fallback)")
            return _wrap_llm_call(llm, fallback_factory=_create_ollama_llm)
        except Exception as e:
            logger.warning(f"⚠️ Gemini indisponível ({e}), usando Ollama como fallback final")
            _stats["fallbacks"] += 1
            return _create_ollama_llm()

    elif complexity == Complexity.HEAVY:
        # Como o Claude está com restrição/404 na API Key do usuário, roteamos HEAVY para o estável Gemini 2.5 Flash
        try:
            llm = _create_gemini_llm()
            logger.info("🟡 Modelo: Gemini 2.5 Flash (HEAVY)")
            return _wrap_llm_call(llm, fallback_factory=_create_ollama_llm)
        except Exception as e:
            logger.warning(f"⚠️ Gemini indisponível ({e}), usando Ollama como fallback")
            _stats["fallbacks"] += 1
            return _create_ollama_llm()
    
    # Fallback final
    return _create_ollama_llm()


def get_llm_for_message(mensagem: str) -> tuple[LLM, Complexity]:
    """
    Conveniência: classifica a mensagem e retorna o LLM + complexidade.
    
    Returns:
        Tupla (LLM, Complexity)
    """
    complexity = classify_complexity(mensagem)
    llm = get_llm(complexity)
    return llm, complexity


# ─── FUNÇÕES DE DIAGNÓSTICO ──────────────────────────────────────────────

def get_stats() -> dict:
    """Retorna estatísticas de uso dos modelos."""
    return dict(_stats)


def get_available_models() -> dict:
    """Verifica quais modelos estão disponíveis e retorna um dict de status."""
    status = {}
    
    # Ollama local
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        status["ollama"] = r.status_code == 200
    except Exception:
        status["ollama"] = False
    
    # Groq
    status["groq"] = bool(GROQ_API_KEY)

    # Gemini
    status["gemini"] = bool(GEMINI_API_KEY)

    # Claude
    status["claude"] = bool(ANTHROPIC_API_KEY)
    
    return status


def diagnostico() -> str:
    """Retorna uma string formatada com o diagnóstico completo do sistema multi-modelo."""
    modelos = get_available_models()
    stats = get_stats()
    
    linhas = [
        "🧠 **Diagnóstico do Sistema Multi-Modelo Hermes v2**\n",
        "**Modelos Disponíveis:**",
        f"  {'✅' if modelos['ollama'] else '❌'} Ollama Local (hermes_llama) — SIMPLE",
        f"  {'✅' if modelos['groq'] else '❌'} Groq llama-3.3-70b-versatile — MEDIUM (primário)",
        f"  {'✅' if modelos['gemini'] else '❌'} Gemini 2.5 Flash — MEDIUM (fallback) / HEAVY",
        f"  {'✅' if modelos['claude'] else '❌'} Claude Sonnet 4 — HEAVY (quando disponível)",
        "",
        "**Estatísticas de Uso (sessão atual):**",
        f"  🟢 Simple:  {stats['simple']} chamadas",
        f"  🟡 Medium:  {stats['medium']} chamadas",
        f"  🔴 Heavy:   {stats['heavy']} chamadas",
        f"  ⚠️ Fallbacks: {stats['fallbacks']} vezes",
    ]
    
    return "\n".join(linhas)


# ─── TESTE LOCAL ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO)
    
    testes = [
        "bebi 500ml de agua",
        "peso 82.5kg",
        "sync hevy",
        "/ajuda",
        "sim",
        "me explique o que é kubernetes",
        "pesquise sobre tendências de IA em 2026",
        "adicionar tarefa no backlog do SisHealth",
        "planejar meus estudos da semana com foco em provas",
        "criar um blueprint de arquitetura para o App Familiar com autenticação OAuth2",
        "quero criar um aplicativo novo do zero chamado FinanceTracker com dashboard React",
    ]
    
    print("🧪 Teste de Classificação de Complexidade:\n")
    for msg in testes:
        comp = classify_complexity(msg)
        emoji = {"simple": "🟢", "medium": "🟡", "heavy": "🔴"}[comp.value]
        print(f"  {emoji} [{comp.value.upper():6s}] \"{msg}\"")
    
    print(f"\n{diagnostico()}")
