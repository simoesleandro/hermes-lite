import os
import sqlite3

_DEFAULT_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "sentinela", "data", "sentinela_rj.db")
)
SENTINELA_DB = os.getenv("SENTINELA_DB_PATH", _DEFAULT_DB)

_OFFLINE_RESUMO = {
    "contratos": None,
    "valor_total": None,
    "alertas_abertos": None,
    "ultima_coleta": None,
    "fornecedores": None,
    "offline": True,
}


def _connect() -> sqlite3.Connection:
    if not os.path.exists(SENTINELA_DB):
        raise FileNotFoundError(f"Banco não encontrado: {SENTINELA_DB}")
    conn = sqlite3.connect(f"file:{SENTINELA_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class SentinelaClient:
    def get_resumo(self) -> dict:
        try:
            conn = _connect()
            row = conn.execute(
                "SELECT COUNT(*) AS contratos, SUM(valor_global) AS valor_total FROM contratos"
            ).fetchone()
            alertas = conn.execute(
                "SELECT COUNT(*) FROM alertas WHERE status = 'aberto'"
            ).fetchone()[0]
            ultima = conn.execute(
                "SELECT MAX(finalizado_em) FROM coletas_log"
            ).fetchone()[0]
            fornecedores = conn.execute(
                "SELECT COUNT(DISTINCT ni) FROM fornecedores"
            ).fetchone()[0]
            conn.close()
            return {
                "contratos": row["contratos"],
                "valor_total": row["valor_total"],
                "alertas_abertos": alertas,
                "ultima_coleta": ultima,
                "fornecedores": fornecedores,
                "offline": False,
            }
        except Exception:
            return dict(_OFFLINE_RESUMO)

    def get_alertas(self, severidade: str = None, limit: int = 10) -> list:
        try:
            conn = _connect()
            if severidade:
                rows = conn.execute(
                    """
                    SELECT a.tipo, a.severidade, a.descricao, a.metodologia,
                           f.razao_social AS fornecedor, c.valor_global AS valor,
                           c.data_assinatura AS data
                    FROM alertas a
                    JOIN contratos c ON a.numero_controle_pncp = c.numero_controle_pncp
                    LEFT JOIN fornecedores f ON c.fornecedor_ni = f.ni
                    WHERE a.status = 'aberto' AND a.severidade = ?
                    ORDER BY c.valor_global DESC
                    LIMIT ?
                    """,
                    (severidade.lower(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT a.tipo, a.severidade, a.descricao, a.metodologia,
                           f.razao_social AS fornecedor, c.valor_global AS valor,
                           c.data_assinatura AS data
                    FROM alertas a
                    JOIN contratos c ON a.numero_controle_pncp = c.numero_controle_pncp
                    LEFT JOIN fornecedores f ON c.fornecedor_ni = f.ni
                    WHERE a.status = 'aberto'
                    ORDER BY
                        CASE a.severidade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END,
                        c.valor_global DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def buscar_fornecedor(self, nome_ou_cnpj: str) -> list:
        try:
            conn = _connect()
            termo = f"%{nome_ou_cnpj}%"
            rows = conn.execute(
                """
                SELECT f.razao_social AS fornecedor, f.ni AS cnpj,
                       c.objeto, c.valor_global AS valor,
                       c.data_assinatura AS data,
                       c.categoria_processo_nome AS categoria,
                       COUNT(a.id) AS alertas
                FROM contratos c
                JOIN fornecedores f ON c.fornecedor_ni = f.ni
                LEFT JOIN alertas a ON c.numero_controle_pncp = a.numero_controle_pncp
                WHERE f.razao_social LIKE ? OR f.ni = ?
                GROUP BY c.numero_controle_pncp
                ORDER BY c.valor_global DESC
                LIMIT 20
                """,
                (termo, nome_ou_cnpj),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def top_contratos(self, limit: int = 5) -> list:
        try:
            conn = _connect()
            rows = conn.execute(
                """
                SELECT f.razao_social AS fornecedor,
                       c.objeto, c.valor_global AS valor,
                       c.data_assinatura, c.categoria_processo_nome AS categoria,
                       COUNT(a.id) AS alertas
                FROM contratos c
                LEFT JOIN fornecedores f ON c.fornecedor_ni = f.ni
                LEFT JOIN alertas a ON c.numero_controle_pncp = a.numero_controle_pncp
                GROUP BY c.numero_controle_pncp
                ORDER BY c.valor_global DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_estatisticas(self) -> dict:
        try:
            conn = _connect()
            por_categoria = conn.execute(
                """
                SELECT categoria_processo_nome AS categoria,
                       COUNT(*) AS contratos,
                       SUM(valor_global) AS valor_total,
                       AVG(valor_global) AS valor_medio,
                       MAX(valor_global) AS valor_maximo
                FROM contratos
                GROUP BY categoria_processo_nome
                ORDER BY valor_total DESC
                """
            ).fetchall()
            por_mes = conn.execute(
                """
                SELECT substr(data_assinatura, 1, 7) AS mes,
                       COUNT(*) AS contratos,
                       SUM(valor_global) AS valor_total
                FROM contratos
                WHERE data_assinatura IS NOT NULL
                  AND data_assinatura >= date('now', '-6 months')
                GROUP BY mes
                ORDER BY mes DESC
                """
            ).fetchall()
            por_severidade = conn.execute(
                "SELECT severidade, COUNT(*) AS total FROM alertas GROUP BY severidade"
            ).fetchall()
            conn.close()
            return {
                "por_categoria": [dict(r) for r in por_categoria],
                "por_mes": [dict(r) for r in por_mes],
                "alertas_por_severidade": [dict(r) for r in por_severidade],
                "offline": False,
            }
        except Exception:
            return {"offline": True}
