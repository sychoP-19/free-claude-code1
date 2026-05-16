"""Resume-based job matching engine and Gmail notification."""

from __future__ import annotations

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from job_agent.resume_parser import extract_keywords


def match_job(job_title: str, job_desc: str, keywords: list[str]) -> int:
    """Return match score 0-100 based on keyword overlap with resume."""
    if not keywords:
        return 50
    text = f"{job_title} {job_desc}".lower()
    matched = sum(1 for kw in keywords if kw.lower() in text)
    return min(100, int((matched / len(keywords)) * 100))


def filter_by_language(
    job_text: str, enabled_languages: dict[str, bool]
) -> list[str]:
    """Return list of matching language tags based on job text."""
    lang_map = {
        "arabic": r"[؀-ۿ]",
        "french": r"\b(fr|fran[cç]ais|bonjour|merci|poste|stage)\b",
        "spanish": r"\b(espa[ñn]ol|puesto|trabajo|experiencia|requisitos)\b",
    }
    matches: list[str] = []
    for lang, enabled in enabled_languages.items():
        if enabled and lang in lang_map and re.search(lang_map[lang], job_text, re.I):
            matches.append(lang.capitalize())
    if enabled_languages.get("english", True) and not matches:
        matches.append("English")
    elif not matches:
        matches.append("English")
    return matches


def send_email_notification(
    smtp_user: str,
    smtp_pass: str,
    to_email: str,
    new_jobs_count: int,
    pending_count: int,
) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"JobAgent Pro — {new_jobs_count} new jobs found"
        msg["From"] = smtp_user
        msg["To"] = to_email
        html = f"""<html><body style="font-family:Arial;color:#333;">
<h2>JobAgent Pro Daily Report</h2>
<p>New jobs today: <strong>{new_jobs_count}</strong></p>
<p>Pending approval: <strong>{pending_count}</strong></p>
<p>Open JobAgent Pro to review and approve matches.</p>
<hr><p style="color:#888;font-size:12px;">JobAgent Pro</p>
</body></html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception:
        return False