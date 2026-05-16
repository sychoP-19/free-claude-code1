"""Scraper for Arabic-market job boards (Bayt.com, NaukriGulf, Wzayef)."""

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


def scrape_bayt(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "-".join(keywords[:2])
        resp = requests.get(
            f"https://www.bayt.com/en/international/jobs/{query}-jobs/",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("li[data-js-job-card]")[:20]:
            title_el = card.select_one("h2 a")
            company_el = card.select_one(".company-name")
            loc_el = card.select_one(".location")
            if title_el:
                href = title_el.get("href", "")
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": loc_el.text.strip() if loc_el else "Middle East",
                    "source": "Bayt.com",
                    "url": f"https://www.bayt.com{href}" if href else "",
                    "description": "",
                    "languages": ["English", "Arabic"],
                })
    except Exception:
        pass
    return jobs


def scrape_naukri_gulf(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "+".join(keywords[:3])
        resp = requests.get(
            f"https://www.naukrigulf.com/{query}-jobs-in-gulf",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".job-card")[:20]:
            title_el = card.select_one(".job-title")
            company_el = card.select_one(".company-name")
            loc_el = card.select_one(".location")
            if title_el:
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": loc_el.text.strip() if loc_el else "Gulf",
                    "source": "NaukriGulf",
                    "url": "",
                    "description": "",
                    "languages": ["English", "Arabic"],
                })
    except Exception:
        pass
    return jobs


def scrape_wzayef(keywords: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    try:
        query = "+".join(keywords[:2])
        resp = requests.get(
            f"https://www.wzayef.com/search?q={query}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".job-item")[:20]:
            title_el = card.select_one(".job-title a")
            company_el = card.select_one(".company-name")
            if title_el:
                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "",
                    "location": "Middle East / Remote",
                    "source": "Wzayef",
                    "url": title_el.get("href", ""),
                    "description": "",
                    "languages": ["Arabic"],
                })
    except Exception:
        pass
    return jobs


def run(keywords: list[str]) -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    all_jobs.extend(scrape_bayt(keywords))
    all_jobs.extend(scrape_naukri_gulf(keywords))
    all_jobs.extend(scrape_wzayef(keywords))
    return all_jobs