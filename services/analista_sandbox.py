import base64
import json
import os
import site
import subprocess
import sys
import tempfile

SENTINELA_DB = r"C:\Users\Leand\OneDrive\Desktop\Sentinela\data\sentinela_rj.db"
SYSHEALTH_DB = r"C:\Users\Leand\onedrive\desktop\projeto_fit\nutricao.db"

BLOCKED = [
    "subprocess", "os.system", "shutil",
    "socket", "__import__", "eval(", "exec(",
    "open(", "pathlib",
]


def _build_script(code_b64: str) -> str:
    return f"""import sys, io, base64 as _b64, json as _json, traceback as _tb
import sqlite3, json, datetime, math, statistics, collections, itertools, re, csv
import time

SENTINELA_DB = {repr(SENTINELA_DB)}
SYSHEALTH_DB = {repr(SYSHEALTH_DB)}


_captured = io.StringIO()
sys.stdout = _captured
_chart_b64 = None
_exec_error = None

_t0 = time.time()
_code = _b64.b64decode({repr(code_b64)}).decode('utf-8')
try:
    exec(compile(_code, '<analista>', 'exec'), globals())
except Exception as _exc:
    _exec_error = ''.join(_tb.format_exception(type(_exc), _exc, _exc.__traceback__))
finally:
    sys.stdout = sys.__stdout__
    print(f"[sandbox] tempo: {{time.time()-_t0:.1f}}s", file=sys.__stderr__)

try:
    import matplotlib.pyplot as _plt
    if _exec_error is None and _plt.get_fignums():
        _buf = io.BytesIO()
        _plt.savefig(_buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0d1117')
        _buf.seek(0)
        _chart_b64 = _b64.b64encode(_buf.read()).decode()
        _plt.close('all')
except Exception:
    pass

print(_json.dumps({{
    "success": _exec_error is None,
    "output": _captured.getvalue(),
    "chart_b64": _chart_b64,
    "error": _exec_error,
}}))
"""


def execute_code(code: str, timeout: int = 60) -> dict:
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

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([
            r"C:\Users\Leand\AppData\Local\Programs\Python\Python313\Lib\site-packages",
            r"C:\Users\Leand\AppData\Roaming\Python\Python313\site-packages",
        ])
        result = subprocess.run(
            [sys.executable, tmp],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
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
