"""github_trending_agent.py — GitHub trending repos via Search API (free, 60 req/hr)."""
import asyncio
import subprocess
from pathlib import Path

import httpx

_API_URL = "https://api.github.com/search/repositories"
_AI_REPOS_DIR = Path(__file__).parent.parent.parent / "ai-repositories"
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


async def get_trending(query: str = "stars:>500", language: str = "", limit: int = 20) -> list[dict]:
    q = query
    if language:
        q = f"{q} language:{language}"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": min(limit, 30)}
    try:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
            r = await client.get(_API_URL, params=params)
            r.raise_for_status()
            items = r.json().get("items", [])
    except Exception as exc:
        return [{"error": str(exc)}]

    return [
        {
            "name": repo["full_name"],
            "description": repo.get("description") or "",
            "stars": repo["stargazers_count"],
            "language": repo.get("language") or "",
            "url": repo["html_url"],
            "clone_url": repo["clone_url"],
            "topics": repo.get("topics", []),
            "installed": (_AI_REPOS_DIR / repo["name"].split("/")[-1]).exists(),
        }
        for repo in items
    ]


def _run_git_clone(clone_url: str, dest: str) -> subprocess.CompletedProcess:
    # Safe: list args, no shell=True
    return subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, dest],
        capture_output=True, text=True, timeout=120,
    )


def _run_pip_install(req_txt: str, cwd: str) -> subprocess.CompletedProcess:
    # Safe: list args, no shell=True
    return subprocess.run(
        ["uv", "pip", "install", "-r", req_txt],
        capture_output=True, text=True, timeout=300, cwd=cwd,
    )


async def clone_repo(clone_url: str) -> dict:
    """Clone a GitHub repo (depth=1) into ai-repositories/."""
    if not clone_url.startswith("https://github.com/"):
        return {"ok": False, "error": "Only github.com URLs are allowed."}

    repo_name = clone_url.rstrip("/").split("/")[-1].removesuffix(".git")
    dest = _AI_REPOS_DIR / repo_name

    if dest.exists():
        return {"ok": True, "message": f"{repo_name} already cloned.", "path": str(dest)}

    _AI_REPOS_DIR.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_git_clone, clone_url, str(dest))
    if result.returncode == 0:
        return {"ok": True, "message": f"Cloned {repo_name}.", "path": str(dest)}
    return {"ok": False, "error": result.stderr}


async def install_repo(repo_name: str) -> dict:
    """Run uv pip install in the repo directory."""
    dest = _AI_REPOS_DIR / repo_name
    if not dest.exists():
        return {"ok": False, "error": f"Repo {repo_name} not found in ai-repositories/."}

    req_txt = dest / "requirements.txt"
    if not req_txt.exists():
        return {"ok": True, "message": "No requirements.txt found — nothing to install."}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_pip_install, str(req_txt), str(dest))
    if result.returncode == 0:
        return {"ok": True, "message": f"Dependencies installed for {repo_name}."}
    return {"ok": False, "error": result.stderr}
