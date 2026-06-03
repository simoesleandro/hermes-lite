import base64
import json
import os
import subprocess
import sys
import tempfile

SENTINELA_DB = r"C:\Users\Leand\onedrive\desktop\sentinela\data\sentinela_rj.db"
SYSHEALTH_DB = r"C:\Users\Leand\onedrive\desktop\projeto_fit\nutricao.db"

BLOCKED = [
    "subprocess", "os.system", "shutil",
    "socket", "__import__", "eval(", "exec(",
    "open(", "pathlib",
]


def _build_script(code_b64: str) -> str:
    return f"""import sys, io, base64 as _b64, json as _json, traceback as _tb
import pandas, numpy
import matplotlib as _mpl
_mpl.use('Agg')
import matplotlib.pyplot as plt
import seaborn
import sqlite3, json, datetime, math, statistics, collections, itertools, re, csv

SENTINELA_DB = {repr(SENTINELA_DB)}
SYSHEALTH_DB = {repr(SYSHEALTH_DB)}


def save_chart():
    _buf = io.BytesIO()
    plt.savefig(_buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0d1117')
    _buf.seek(0)
    return _b64.b64encode(_buf.read()).decode()


_captured = io.StringIO()
sys.stdout = _captured
_chart_b64 = None
_exec_error = None

_code = _b64.b64decode({repr(code_b64)}).decode('utf-8')
try:
    exec(compile(_code, '<analista>', 'exec'), globals())
except Exception as _exc:
    _exec_error = ''.join(_tb.format_exception(type(_exc), _exc, _exc.__traceback__))
finally:
    sys.stdout = sys.__stdout__

if _exec_error is None and plt.get_fignums():
    _chart_b64 = save_chart()
    plt.close('all')

print(_json.dumps({{
    "success": _exec_error is None,
    "output": _captured.getvalue(),
    "chart_b64": _chart_b64,
    "error": _exec_error,
}}))
"""


def execute_code(code: str, timeout: int = 30) -> dict:
    for blocked in BLOCKED:
        if blocked in code:
            return {
                "success": False,
                "error": f"Operação bloqueada: '{blocked}' não é permitido.",
                "output": "",
                "chart_b64": None,
            }

    code_b64 = base64.b64encode(code.encode("utf-8")).decode()
    script = _build_script(code_b64)

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            tmp = f.name

        result = subprocess.run(
            [sys.executable, tmp],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        stdout = result.stdout.strip()
        if not stdout:
            return {
                "success": False,
                "error": (result.stderr[:500] or "Sem saída do processo"),
                "output": "",
                "chart_b64": None,
            }

        return json.loads(stdout)

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Tempo limite de {timeout}s excedido.",
            "output": "",
            "chart_b64": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output": "",
            "chart_b64": None,
        }
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
