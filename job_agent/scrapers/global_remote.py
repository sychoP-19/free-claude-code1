"""Scraper for global remote job boards (RemoteOK, WeWorkRemotely, LinkedIn)."""

from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 30


def scrape_remote_ok(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        resp = requests.get(
            "https://remoteok.com/api", headers=HEADERS, timeout=TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data[:50]:
            if isinstance(item, dict) and "id" in item:
                title = item.get("position", "")
                desc = item.get("description", "")
                jobs.append({
                    "title": title,
                    "company": item.get("company", ""),
                    "location": "Remote",
                    "source": "RemoteOK",
                    "url": item.get("url", ""),
                    "description": desc,
                    "languages": ["English"],
                })
    except Exception:
        pass
    return jobs


def scrape_we_work_remotely(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "+".join(keywords[:3])
        resp = requests.get(
            f"https://weworkremotely.com/remote-jobs/search?term={query}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for li in soup.select("li.job")[:30]:
            title_el = li.select_one("span.title")
            company_el = li.select_one("span.company")
            link_el = li.select_one("a[href*='/remote-jobs/']")
            if title_el:
                href = link_el["href"] if link_el else ""
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": "Remote",
                    "source": "WeWorkRemotely",
                    "url": f"https://weworkremotely.com{href}" if href else "",
                    "description": "",
                    "languages": ["English"],
                })
    except Exception:
        pass
    return jobs


def scrape_linkedin_global(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "+".join(keywords[:3])
        resp = requests.get(
            f"https://www.linkedin.com/jobs/search/?keywords={query}"
            "&location=Worldwide&geoId=92000000&f_WT=2",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".base-card")[:20]:
            title_el = card.select_one(".base-search-card__title")
            company_el = card.select_one(".base-search-card__subtitle")
            link_el = card.select_one("a.base-card__full-link")
            if title_el:
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": "Remote / Global",
                    "source": "LinkedIn",
                    "url": link_el["href"] if link_el else "",
                    "description": "",
                    "languages": ["English"],
                })
    except Exception:
        pass
    return jobs


def run(keywords: list[str]) -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    all_jobs.extend(scrape_remote_ok(keywords))
    all_jobs.extend(scrape_we_work_remotely(keywords))
    all_jobs.extend(scrape_linkedin_global(keywords))
    return all_jobs