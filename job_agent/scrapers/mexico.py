"""Scraper for Mexico job boards (Computrabajo, Indeed Mexico, OCC Mundial)."""

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


def scrape_computrabajo(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "+".join(keywords[:2])
        resp = requests.get(
            f"https://www.computrabajo.com.mx/trabajo-de-{query}",
            headers=HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("article.js-job")[:20]:
            title_el = card.select_one("h2 a")
            company_el = card.select_one(".empresa")
            loc_el = card.select_one(".ubicacion")
            if title_el:
                href = title_el.get("href", "")
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": loc_el.text.strip() if loc_el else "Mexico",
                    "source": "Computrabajo",
                    "url": f"https://www.computrabajo.com.mx{href}" if href else "",
                    "description": "",
                    "languages": ["Spanish"],
                })
    except Exception:
        pass
    return jobs


def scrape_indeed_mexico(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "+".join(keywords[:3])
        resp = requests.get(
            f"https://mx.indeed.com/jobs?q={query}",
            headers=HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".job_seen_beacon")[:20]:
            title_el = card.select_one("h2 a")
            company_el = card.select_one(".companyName")
            loc_el = card.select_one(".companyLocation")
            if title_el:
                href = title_el.get("href", "")
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": loc_el.text.strip() if loc_el else "Mexico",
                    "source": "Indeed Mexico",
                    "url": f"https://mx.indeed.com{href}" if href else "",
                    "description": "",
                    "languages": ["Spanish"],
                })
    except Exception:
        pass
    return jobs


def scrape_occ_mundial(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "+".join(keywords[:2])
        resp = requests.get(
            f"https://www.occ.com.mx/empleos/?q={query}",
            headers=HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".job-item")[:20]:
            title_el = card.select_one(".job-title a")
            company_el = card.select_one(".company-name")
            loc_el = card.select_one(".job-location")
            if title_el:
                href = title_el.get("href", "")
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": loc_el.text.strip() if loc_el else "Mexico",
                    "source": "OCC Mundial",
                    "url": f"https://www.occ.com.mx{href}" if href else "",
                    "description": "",
                    "languages": ["Spanish"],
                })
    except Exception:
        pass
    return jobs


def run(keywords: list[str]) -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    all_jobs.extend(scrape_computrabajo(keywords))
    all_jobs.extend(scrape_indeed_mexico(keywords))
    all_jobs.extend(scrape_occ_mundial(keywords))
    return all_jobs