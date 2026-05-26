"""email_digest_agent.py — Daily/weekly email digest compilation and dispatch."""
from __future__ import annotations

import json
import logging
import platform
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent
DIGESTS_DIR = BASE / "data" / "digests"
DIGESTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DigestData:
    period: str
    generated_at: str
    trending_topics: list[dict] = field(default_factory=list)
    revenue_summary: dict = field(default_factory=dict)
    pipeline_outputs_count: int = 0
    system_health: dict = field(default_factory=dict)
    services_status: dict = field(default_factory=dict)
    gmail_sent: bool = False


class EmailDigestAgent:
    """Compiles a JARVIS intelligence digest and sends it via Gmail (or saves locally)."""

    async def run(self, period: str = "daily") -> DigestData:
        now = datetime.now(timezone.utc).isoformat()
        trending = await self._get_trending()
        revenue = await self._get_revenue()
        outputs_count = self._count_outputs()
        health = self._system_health()
        services = await self._services_status()

        digest = DigestData(
            period=period,
            generated_at=now,
            trending_topics=trending,
            revenue_summary=revenue,
            pipeline_outputs_count=outputs_count,
            system_health=health,
            services_status=services,
        )

        html = self._render_html(digest)
        sent = self._send_email(html, period)
        self._save_digest(digest, html)

        if sent:
            digest = DigestData(
                period=digest.period,
                generated_at=digest.generated_at,
                trending_topics=digest.trending_topics,
                revenue_summary=digest.revenue_summary,
                pipeline_outputs_count=digest.pipeline_outputs_count,
                system_health=digest.system_health,
                services_status=digest.services_status,
                gmail_sent=True,
            )

        return digest

    # ── Data gathering ─────────────────────────────────────────────────────

    async def _get_trending(self) -> list[dict]:
        try:
            from agents.trending_agent import get_trending_topics
            return await get_trending_topics(limit=10)
        except Exception as e:
            logger.warning("trending fetch failed: %s", e)
            return [{"title": "Trending data unavailable", "source": "error"}]

    async def _get_revenue(self) -> dict:
        rev_file = BASE / "data" / "revenue.json"
        if rev_file.exists():
            try:
                return json.loads(rev_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"monthly_target": 0, "current": 0, "subscribers": 0, "note": "No revenue data yet"}

    def _count_outputs(self) -> int:
        outputs_dir = BASE / "outputs"
        if not outputs_dir.exists():
            return 0
        count = 0
        for p in outputs_dir.rglob("*"):
            if p.is_file():
                count += 1
        return count

    def _system_health(self) -> dict:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        root = "C:\\" if sys.platform == "win32" else "/"
        disk = psutil.disk_usage(root)
        return {
            "cpu_percent": round(cpu),
            "mem_percent": round(mem.percent),
            "mem_used_gb": round(mem.used / (1024 ** 3), 1),
            "mem_total_gb": round(mem.total / (1024 ** 3), 1),
            "disk_percent": round(disk.percent),
            "platform": platform.platform(),
        }

    async def _services_status(self) -> dict:
        import asyncio
        import httpx

        checks: dict[str, str] = {}
        services = [
            ("Ollama", "http://localhost:11434/api/tags"),
            ("Proxy", "http://localhost:8082/v1/models"),
        ]

        async def _check(name: str, url: str) -> tuple[str, str]:
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(url)
                    return name, "online" if r.status_code < 500 else "degraded"
            except Exception:
                return name, "offline"

        results = await asyncio.gather(*[_check(n, u) for n, u in services])
        for name, status in results:
            checks[name] = status
        return checks

    # ── Email rendering ─────────────────────────────────────────────────────

    def _render_html(self, digest: DigestData) -> str:
        period_label = "WEEKLY" if digest.period == "weekly" else "DAILY"
        date_str = datetime.now().strftime("%A, %B %d, %Y")

        topic_rows = ""
        for t in digest.trending_topics[:10]:
            title = t.get("title", "—")
            source = t.get("source", "")
            url = t.get("url", "")
            if url:
                topic_rows += f'<tr><td style="padding:6px 10px;border-bottom:1px solid #1e293b;"><a href="{url}" style="color:#60a5fa;text-decoration:none;">{title}</a></td><td style="padding:6px 10px;border-bottom:1px solid #1e293b;color:#94a3b8;">{source}</td></tr>'
            else:
                topic_rows += f'<tr><td style="padding:6px 10px;border-bottom:1px solid #1e293b;color:#e2e8f0;">{title}</td><td style="padding:6px 10px;border-bottom:1px solid #1e293b;color:#94a3b8;">{source}</td></tr>'

        rev = digest.revenue_summary
        health = digest.system_health
        services = digest.services_status

        service_badges = ""
        for name, status in services.items():
            color = "#22c55e" if status == "online" else "#ef4444" if status == "offline" else "#f59e0b"
            service_badges += f'<span style="display:inline-block;padding:3px 10px;margin:2px 4px;border-radius:12px;background:{color}22;border:1px solid {color};color:{color};font-size:12px;">{name}: {status}</span>'

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:24px 16px;">

  <!-- HEADER -->
  <div style="text-align:center;padding:24px 0;border-bottom:2px solid #1e293b;">
    <h1 style="margin:0;font-size:28px;letter-spacing:4px;color:#60a5fa;">JARVIS</h1>
    <p style="margin:4px 0 0;font-size:12px;letter-spacing:2px;color:#64748b;">CONTENT INTELLIGENCE</p>
    <p style="margin:8px 0 0;font-size:11px;color:#475569;">{period_label} DIGEST &middot; {date_str}</p>
  </div>

  <!-- TRENDING -->
  <div style="margin:24px 0;">
    <h2 style="font-size:14px;letter-spacing:2px;color:#60a5fa;margin:0 0 12px;">TRENDING TOPICS</h2>
    <table style="width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;">
      <thead><tr style="background:#0f172a;"><th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;">TOPIC</th><th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;">SOURCE</th></tr></thead>
      <tbody>{topic_rows or '<tr><td colspan="2" style="padding:12px;color:#64748b;text-align:center;">No trending data</td></tr>'}</tbody>
    </table>
  </div>

  <!-- REVENUE -->
  <div style="margin:24px 0;">
    <h2 style="font-size:14px;letter-spacing:2px;color:#22c55e;margin:0 0 12px;">REVENUE OVERVIEW</h2>
    <div style="background:#1e293b;border-radius:8px;padding:16px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <span style="color:#94a3b8;font-size:13px;">Current Revenue</span>
        <span style="color:#22c55e;font-size:18px;font-weight:600;">${rev.get("current", 0):,.0f}</span>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <span style="color:#94a3b8;font-size:13px;">Monthly Target</span>
        <span style="color:#e2e8f0;font-size:14px;">${rev.get("monthly_target", 0):,.0f}</span>
      </div>
      <div style="display:flex;justify-content:space-between;">
        <span style="color:#94a3b8;font-size:13px;">Subscribers</span>
        <span style="color:#e2e8f0;font-size:14px;">{rev.get("subscribers", 0):,}</span>
      </div>
    </div>
  </div>

  <!-- PIPELINE OUTPUTS -->
  <div style="margin:24px 0;">
    <h2 style="font-size:14px;letter-spacing:2px;color:#a78bfa;margin:0 0 12px;">PIPELINE OUTPUTS</h2>
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <span style="font-size:36px;font-weight:700;color:#a78bfa;">{digest.pipeline_outputs_count}</span>
      <span style="display:block;font-size:12px;color:#64748b;margin-top:4px;">total files in outputs/</span>
    </div>
  </div>

  <!-- SYSTEM HEALTH -->
  <div style="margin:24px 0;">
    <h2 style="font-size:14px;letter-spacing:2px;color:#f59e0b;margin:0 0 12px;">SYSTEM HEALTH</h2>
    <div style="background:#1e293b;border-radius:8px;padding:16px;">
      <div style="margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
          <span style="color:#94a3b8;">CPU</span><span style="color:#e2e8f0;">{health.get("cpu_percent", 0)}%</span>
        </div>
        <div style="background:#0f172a;border-radius:4px;height:6px;overflow:hidden;">
          <div style="background:#60a5fa;width:{health.get("cpu_percent", 0)}%;height:100%;border-radius:4px;"></div>
        </div>
      </div>
      <div style="margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
          <span style="color:#94a3b8;">Memory</span><span style="color:#e2e8f0;">{health.get("mem_percent", 0)}% ({health.get("mem_used_gb", 0)}/{health.get("mem_total_gb", 0)} GB)</span>
        </div>
        <div style="background:#0f172a;border-radius:4px;height:6px;overflow:hidden;">
          <div style="background:#22c55e;width:{health.get("mem_percent", 0)}%;height:100%;border-radius:4px;"></div>
        </div>
      </div>
      <div>
        <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
          <span style="color:#94a3b8;">Disk</span><span style="color:#e2e8f0;">{health.get("disk_percent", 0)}%</span>
        </div>
        <div style="background:#0f172a;border-radius:4px;height:6px;overflow:hidden;">
          <div style="background:#f59e0b;width:{health.get("disk_percent", 0)}%;height:100%;border-radius:4px;"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- SERVICES -->
  <div style="margin:24px 0;">
    <h2 style="font-size:14px;letter-spacing:2px;color:#60a5fa;margin:0 0 12px;">SERVICES</h2>
    <div style="background:#1e293b;border-radius:8px;padding:12px;">{service_badges or '<span style="color:#64748b;font-size:13px;">No service data</span>'}</div>
  </div>

  <!-- FOOTER -->
  <div style="text-align:center;padding:24px 0;border-top:1px solid #1e293b;margin-top:24px;">
    <p style="margin:0;font-size:11px;color:#475569;">Generated by JARVIS Content Intelligence &middot; {digest.generated_at}</p>
  </div>

</div>
</body></html>"""

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def _send_email(self, html: str, period: str) -> bool:
        try:
            from integrations.gmail_client import send_notification
            label = "Weekly" if period == "weekly" else "Daily"
            subject = f"JARVIS {label} Digest — {datetime.now().strftime('%b %d, %Y')}"
            return send_notification(subject=subject, body=html)
        except Exception as e:
            logger.warning("Gmail send failed, digest saved locally: %s", e)
            return False

    def _save_digest(self, digest: DigestData, html: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = DIGESTS_DIR / f"digest_{ts}_{digest.period}.json"
        html_path = DIGESTS_DIR / f"digest_{ts}_{digest.period}.html"

        data = asdict(digest)
        data["html_file"] = html_path.name

        json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")

        logger.info("Digest saved: %s", json_path.name)
        return json_path

    # ── Helpers for API routes ───────────────────────────────────────────────

    @staticmethod
    def list_digests(limit: int = 20) -> list[dict]:
        if not DIGESTS_DIR.exists():
            return []
        digests: list[dict] = []
        for fp in sorted(DIGESTS_DIR.glob("digest_*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                data["filename"] = fp.name
                digests.append(data)
            except Exception:
                pass
        return digests

    @staticmethod
    def get_digest_html(filename: str) -> str | None:
        path = DIGESTS_DIR / filename
        if path.exists() and path.suffix == ".html":
            return path.read_text(encoding="utf-8")
        # Derive html filename from json entry
        json_path = DIGESTS_DIR / filename
        if json_path.exists() and json_path.suffix == ".json":
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                html_name = data.get("html_file", "")
                if html_name:
                    html_path = DIGESTS_DIR / html_name
                    if html_path.exists():
                        return html_path.read_text(encoding="utf-8")
            except Exception:
                pass
        return None
