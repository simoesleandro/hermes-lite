import json
import os
import sqlite3
import urllib.request

from services.sentinela_client import SENTINELA_DB


def _connect_db():
    if not os.path.exists(SENTINELA_DB):
        raise FileNotFoundError(f"Banco não encontrado: {SENTINELA_DB}")
    conn = sqlite3.connect(f"file:{SENTINELA_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def buscar_cnpj(cnpj: str) -> dict:
    cnpj_digits = "".join(c for c in cnpj if c.isdigit())
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_digits}"
        req = urllib.request.Request(url, headers={"User-Agent": "HermesLite/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return {
            "razao_social": data.get("razao_social"),
            "situacao_cadastral": data.get("descricao_situacao_cadastral"),
            "atividade_principal": data.get("cnae_fiscal_descricao"),
            "socios": [s.get("nome_socio") for s in (data.get("qsa") or [])],
            "data_abertura": data.get("data_inicio_atividade"),
            "capital_social": data.get("capital_social"),
        }
    except Exception as e:
        return {"erro": str(e)}


def buscar_contratos(termo: str) -> list:
    try:
        conn = _connect_db()
        rows = conn.execute(
            """
            SELECT c.numero_controle_pncp, c.objeto, c.valor_global,
                   c.data_assinatura, c.fornecedor_ni,
                   f.razao_social AS fornecedor
            FROM contratos c
            LEFT JOIN fornecedores f ON c.fornecedor_ni = f.ni
            WHERE c.objeto LIKE ? OR f.razao_social LIKE ? OR c.fornecedor_ni = ?
            ORDER BY c.valor_global DESC
            LIMIT 10
            """,
            (f"%{termo}%", f"%{termo}%", termo),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"erro": str(e)}]


def buscar_alertas(termo: str) -> list:
    try:
        conn = _connect_db()
        rows = conn.execute(
            """
            SELECT a.tipo, a.severidade, a.descricao, a.metodologia,
                   f.razao_social AS fornecedor, c.valor_global AS valor
            FROM alertas a
            JOIN contratos c ON a.numero_controle_pncp = c.numero_controle_pncp
            LEFT JOIN fornecedores f ON c.fornecedor_ni = f.ni
            WHERE (f.razao_social LIKE ? OR c.fornecedor_ni = ?)
              AND a.status = 'aberto'
            ORDER BY CASE a.severidade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END
            LIMIT 10
            """,
            (f"%{termo}%", termo),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"erro": str(e)}]


def buscar_web(query: str) -> list:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        return [{"title": r.get("title"), "href": r.get("href"), "body": r.get("body")} for r in results]
    except Exception:
        return []


TOOLS_REGISTRY = {
    "buscar_cnpj":      buscar_cnpj,
    "buscar_contratos": buscar_contratos,
    "buscar_alertas":   buscar_alertas,
    "buscar_web":       buscar_web,
}
