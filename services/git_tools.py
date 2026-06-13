"""Git read-only helpers — contexto para agente Desenvolvimento e MCP."""

import os
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAX_DIFF_LINES = 200


def _run_git(*args: str, timeout: int = 15) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, str(exc)


def git_branch() -> str:
    code, out = _run_git("branch", "--show-current")
    return out if code == 0 else ""


def git_status_short() -> str:
    code, out = _run_git("status", "-sb")
    return out if code == 0 else f"git status falhou: {out}"


def git_diff_stat() -> str:
    code, out = _run_git("diff", "--stat")
    if code != 0:
        return out
    code2, staged = _run_git("diff", "--cached", "--stat")
    if code2 == 0 and staged.strip():
        return out + "\n\n(staged)\n" + staged
    return out


def git_diff(max_lines: int = _MAX_DIFF_LINES, staged: bool = False) -> str:
    args = ("diff", "--cached") if staged else ("diff",)
    code, out = _run_git(*args)
    if code != 0:
        return out
    lines = out.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n… ({len(lines) - max_lines} linhas omitidas)"
    return out


def git_log(n: int = 8) -> str:
    code, out = _run_git(
        "log", f"-{min(n, 20)}", "--oneline", "--decorate", "--no-color",
    )
    return out if code == 0 else out


def format_git_context(include_diff: bool = False) -> str:
    branch = git_branch()
    status = git_status_short()
    if not status and not branch:
        return ""
    parts = ["=== GIT (hermes-lite) ==="]
    if branch:
        parts.append(f"branch: {branch}")
    parts.append(status)
    stat = git_diff_stat()
    if stat:
        parts.extend(["", "=== GIT DIFF --stat ===", stat])
    if include_diff:
        diff = git_diff(max_lines=80)
        if diff:
            parts.extend(["", "=== GIT DIFF (trecho) ===", diff])
    return "\n".join(parts)
