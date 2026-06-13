"""Cliente GitHub API — busca de repositórios e README."""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("hermes.github")

API_BASE = "https://api.github.com"


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Hermes-Lite-Radar/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str, timeout: int = 25) -> dict | list:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def search_repositories(query: str, per_page: int = 15) -> list[dict]:
    qs = urllib.parse.urlencode({
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(per_page, 30),
    })
    try:
        data = _get(f"{API_BASE}/search/repositories?{qs}")
        items = data.get("items", []) if isinstance(data, dict) else []
        return [_normalize_repo(r) for r in items]
    except urllib.error.HTTPError as exc:
        logger.warning("GitHub search falhou (%s): %s", query, exc)
        return []
    except Exception as exc:
        logger.warning("GitHub search erro: %s", exc)
        return []


def _normalize_repo(raw: dict) -> dict:
    return {
        "full_name": raw.get("full_name", ""),
        "html_url": raw.get("html_url", ""),
        "description": (raw.get("description") or "")[:500],
        "stars": raw.get("stargazers_count", 0),
        "language": raw.get("language") or "",
        "topics": raw.get("topics") or [],
        "updated_at": raw.get("updated_at", ""),
        "license": (raw.get("license") or {}).get("spdx_id") if raw.get("license") else None,
    }


def fetch_readme_excerpt(full_name: str, max_chars: int = 1200) -> str:
    if not full_name or "/" not in full_name:
        return ""
    try:
        data = _get(f"{API_BASE}/repos/{full_name}/readme")
        if not isinstance(data, dict):
            return ""
        content = data.get("content", "")
        if not content:
            return ""
        decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        return decoded[:max_chars]
    except Exception:
        return ""


def default_search_queries() -> list[str]:
    raw = os.getenv("GITHUB_RADAR_QUERIES", "").strip()
    if raw:
        return [q.strip() for q in raw.split("|") if q.strip()]
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    return [
        f"topic:mcp stars:>200 pushed:>{week_ago}",
        f"topic:llm stars:>800 language:python pushed:>{week_ago}",
        f"topic:agents stars:>300 pushed:>{month_ago}",
        f"topic:self-hosted stars:>500 language:python pushed:>{month_ago}",
        f"topic:rag stars:>200 pushed:>{month_ago}",
        "hermes OR open-webui OR cursor-agent stars:>1000 language:python",
    ]
