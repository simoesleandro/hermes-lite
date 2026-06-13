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


def github_token_configured() -> bool:
    return bool(os.getenv("GITHUB_TOKEN", "").strip())


def get_authenticated_user() -> dict | None:
    if not github_token_configured():
        return None
    try:
        data = _get(f"{API_BASE}/user")
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("GitHub /user falhou: %s", exc)
        return None


def github_username() -> str:
    explicit = os.getenv("GITHUB_USER", "").strip()
    if explicit:
        return explicit
    user = get_authenticated_user()
    return (user or {}).get("login", "")


def _normalize_issue(item: dict) -> dict:
    repo = ""
    if isinstance(item.get("repository"), dict):
        repo = item["repository"].get("full_name", "")
    elif item.get("repository_url"):
        repo = str(item["repository_url"]).split("/repos/")[-1]
    return {
        "number": item.get("number"),
        "title": (item.get("title") or "")[:120],
        "html_url": item.get("html_url", ""),
        "repo": repo,
        "state": item.get("state"),
        "updated_at": item.get("updated_at", ""),
        "is_pr": bool(item.get("pull_request")),
    }


def search_issues(q: str, per_page: int = 10) -> list[dict]:
    if not github_token_configured():
        return []
    qs = urllib.parse.urlencode({
        "q": q,
        "sort": "updated",
        "order": "desc",
        "per_page": min(per_page, 30),
    })
    try:
        data = _get(f"{API_BASE}/search/issues?{qs}")
        items = data.get("items", []) if isinstance(data, dict) else []
        return [_normalize_issue(i) for i in items]
    except Exception as exc:
        logger.warning("GitHub search issues falhou (%s): %s", q, exc)
        return []


def list_open_prs_by_author(username: str, limit: int = 5) -> list[dict]:
    if not username:
        return []
    return search_issues(f"is:pr is:open author:{username}", per_page=limit)


def list_prs_needing_review(username: str, limit: int = 5) -> list[dict]:
    if not username:
        return []
    return search_issues(f"is:pr is:open review-requested:{username}", per_page=limit)


def list_assigned_issues(limit: int = 8) -> list[dict]:
    if not github_token_configured():
        return []
    try:
        data = _get(
            f"{API_BASE}/issues?filter=assigned&state=open&per_page={min(limit, 30)}"
        )
        if not isinstance(data, list):
            return []
        return [_normalize_issue(i) for i in data if not i.get("pull_request")][:limit]
    except Exception as exc:
        logger.warning("GitHub assigned issues falhou: %s", exc)
        return []


def list_user_repos(username: str, limit: int = 10) -> list[str]:
    if not username:
        return []
    raw = os.getenv("GITHUB_INBOX_REPOS", "").strip()
    if raw:
        return [r.strip() for r in raw.split(",") if r.strip()][:limit]
    try:
        data = _get(
            f"{API_BASE}/users/{username}/repos?"
            f"sort=updated&per_page={min(limit, 30)}&type=owner"
        )
        if not isinstance(data, list):
            return []
        return [r["full_name"] for r in data if r.get("full_name")][:limit]
    except Exception as exc:
        logger.warning("GitHub list repos falhou: %s", exc)
        return []


def latest_failed_run(full_name: str) -> dict | None:
    if not github_token_configured():
        return None
    try:
        data = _get(
            f"{API_BASE}/repos/{full_name}/actions/runs?status=failure&per_page=1"
        )
        runs = data.get("workflow_runs", []) if isinstance(data, dict) else []
        if not runs:
            return None
        run = runs[0]
        return {
            "repo": full_name,
            "name": run.get("name", ""),
            "html_url": run.get("html_url", ""),
            "created_at": run.get("created_at", ""),
            "branch": run.get("head_branch", ""),
        }
    except Exception:
        return None


def list_recent_ci_failures(username: str, max_repos: int = 8, limit: int = 3) -> list[dict]:
    failures: list[dict] = []
    for repo in list_user_repos(username, limit=max_repos):
        failed = latest_failed_run(repo)
        if failed:
            failures.append(failed)
        if len(failures) >= limit:
            break
    return failures


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
