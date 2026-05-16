"""JobAgent Pro — entry point with daily scheduler."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.expanduser("~/jobsoffers/jobagent.log"), encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("jobagent")


def run_search() -> None:
    from job_agent.matcher import send_email_notification
    from job_agent.storage import add_jobs, get_all_jobs, load_settings
    from job_agent.scrapers.orchestrator import run_all

    settings = load_settings()
    kws = settings.get("keywords", [])
    locs = settings.get("locations", {})
    if not kws:
        log.warning("No keywords configured — skipping search")
        return

    log.info("Starting search (keywords=%s, locations=%s)", kws, locs)
    try:
        results = run_all(kws, locs)
        new_count = add_jobs(results)
        log.info("Search complete — %d new jobs found", new_count)

        gmail_user = settings.get("gmail_user", "")
        gmail_pass = settings.get("gmail_pass", "")
        if gmail_user and gmail_pass:
            pending = sum(1 for j in get_all_jobs() if j.get("status") == "New")
            sent = send_email_notification(
                gmail_user, gmail_pass,
                to_email=gmail_user,
                new_jobs_count=new_count,
                pending_count=pending,
            )
            if sent:
                log.info("Email notification sent")
            else:
                log.warning("Email notification failed")
    except Exception:
        log.exception("Search cycle failed")


def scheduler_loop() -> None:
    run_search()
    while True:
        settings = load_settings()
        time_str = settings.get("schedule_time", "08:00")
        try:
            hour, minute = (int(x) for x in time_str.split(":"))
        except (ValueError, TypeError):
            hour, minute = 8, 0

        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()
        log.info("Next search at %s (in %.0f minutes)", target, delay / 60)

        end = time.monotonic() + delay
        while time.monotonic() < end:
            time.sleep(min(60, end - time.monotonic()))
        run_search()


def main() -> None:
    parser = argparse.ArgumentParser(description="JobAgent Pro")
    parser.add_argument("--search", action="store_true", help="Run a single search and exit")
    parser.add_argument("--scheduler", action="store_true", help="Run scheduler loop")
    parser.add_argument("--gui", action="store_true", help="Launch the GUI application")
    args = parser.parse_args()

    if args.search:
        run_search()
    elif args.gui:
        from job_agent.gui.app import run
        run()
    else:
        scheduler_loop()


if __name__ == "__main__":
    main()