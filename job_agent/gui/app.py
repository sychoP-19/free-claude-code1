"""JobAgent Pro — CustomTkinter GUI with dark theme."""

from __future__ import annotations

import threading
from typing import Any

import customtkinter as ctk

from job_agent.storage import (
    add_jobs,
    append_note,
    get_all_jobs,
    get_notes,
    load_settings,
    save_settings,
    update_job_status,
)
from job_agent.scrapers.orchestrator import run_all

# ---- colour tokens -----------------------------------------------------------
PRIMARY = "#1a1a2e"
SECONDARY = "#16213e"
ACCENT = "#0f3460"
CURRENCY = "#e94560"
TEXT = "#eaeaea"
SUBTEXT = "#8899aa"
SUCCESS = "#2ecc71"
WARNING = "#f39c12"
SIDEBAR_W = 220
FONT = "Segoe UI"


class JobAgentApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("JobAgent Pro")
        self.geometry("1280x800")
        self.minsize(1024, 600)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color=PRIMARY)

        self.settings = load_settings()
        self.current_screen: str = "dashboard"
        self._build_ui()
        self._navigate("dashboard")

    # -- layout ----------------------------------------------------------------
    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._build_status_bar()
        self._build_sidebar()
        self._content_frame = ctk.CTkFrame(self, fg_color=PRIMARY, corner_radius=0)
        self._content_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 0))
        self._content_frame.grid_rowconfigure(0, weight=1)
        self._content_frame.grid_columnconfigure(0, weight=1)

    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=32, fg_color=ACCENT, corner_radius=0)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        ctk.CTkLabel(
            bar, text="JobAgent Pro v1.0", font=(FONT, 11),
            text_color=TEXT, fg_color="transparent",
        ).pack(side="left", padx=12)
        self._status_label = ctk.CTkLabel(
            bar, text="Ready", font=(FONT, 11),
            text_color=SUBTEXT, fg_color="transparent",
        )
        self._status_label.pack(side="right", padx=12)

    def _set_status(self, msg: str) -> None:
        self._status_label.configure(text=msg)
        self.update_idletasks()

    def _build_sidebar(self) -> None:
        nav = ctk.CTkFrame(
            self, width=SIDEBAR_W, fg_color=SECONDARY, corner_radius=0,
        )
        nav.grid(row=1, column=0, sticky="ns")
        nav.grid_propagate(False)

        ctk.CTkLabel(
            nav, text="JobAgent Pro", font=(FONT, 18, "bold"),
            text_color=CURRENCY,
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            nav, text="Smart Job Hunting", font=(FONT, 10),
            text_color=SUBTEXT,
        ).pack(pady=(0, 20))

        items = [
            ("dashboard", "Dashboard"),
            ("search", "Search & Results"),
            ("keywords", "Keywords"),
            ("resume", "My Resume"),
            ("approved", "Approved Jobs"),
            ("export", "Export"),
            ("settings", "Settings"),
        ]
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for key, label in items:
            btn = ctk.CTkButton(
                nav, text=label, anchor="w", height=36,
                fg_color="transparent", text_color=TEXT,
                hover_color=ACCENT, corner_radius=6,
                font=(FONT, 13),
                command=lambda k=key: self._navigate(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_btns[key] = btn

    def _navigate(self, screen: str) -> None:
        self.current_screen = screen
        for k, btn in self._nav_btns.items():
            btn.configure(
                fg_color=ACCENT if k == screen else "transparent",
                text_color=CURRENCY if k == screen else TEXT,
            )
        for w in self._content_frame.winfo_children():
            w.destroy()

        builders = {
            "dashboard": self._build_dashboard,
            "search": self._build_search,
            "keywords": self._build_keywords,
            "resume": self._build_resume,
            "approved": self._build_approved,
            "export": self._build_export,
            "settings": self._build_settings,
        }
        builders.get(screen, self._build_dashboard)()

    # -- dashboard -------------------------------------------------------------
    def _build_dashboard(self) -> None:
        frame = ctk.CTkScrollableFrame(
            self._content_frame, fg_color="transparent",
        )
        frame.pack(fill="both", expand=True, padx=24, pady=16)

        ctk.CTkLabel(
            frame, text="Dashboard", font=(FONT, 24, "bold"), text_color=TEXT,
        ).pack(anchor="w", pady=(0, 16))

        jobs = get_all_jobs()
        new_count = sum(1 for j in jobs if j.get("status") == "New")
        approved_count = sum(1 for j in jobs if j.get("status") == "Approved")
        total = len(jobs)
        avg_score = (
            sum(j.get("match_score", 0) or 0 for j in jobs) / total
            if total else 0
        )

        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 20))

        stats = [
            ("New Jobs", str(new_count), ACCENT),
            ("Approved", str(approved_count), SUCCESS),
            ("Total Jobs", str(total), WARNING),
            (f"Avg Match", f"{avg_score:.0f}%", CURRENCY),
        ]
        for title, value, color in stats:
            card = ctk.CTkFrame(
                cards_frame, fg_color=SECONDARY, corner_radius=10,
                border_width=1, border_color=color,
            )
            card.pack(side="left", fill="x", expand=True, padx=6, ipady=12)
            ctk.CTkLabel(
                card, text=title, font=(FONT, 11), text_color=SUBTEXT,
            ).pack(pady=(10, 0))
            ctk.CTkLabel(
                card, text=value, font=(FONT, 28, "bold"), text_color=color,
            ).pack(pady=(2, 10))

        notes_label = ctk.CTkLabel(
            frame, text="Recent Notes", font=(FONT, 16, "bold"),
            text_color=TEXT,
        )
        notes_label.pack(anchor="w", pady=(0, 8))
        notes = get_notes()
        notes_text = "\n".join(notes[-5:]) if notes else "No notes yet."
        notes_box = ctk.CTkTextbox(
            frame, height=120, fg_color=SECONDARY, text_color=TEXT,
            font=(FONT, 12),
        )
        notes_box.insert("0.0", notes_text)
        notes_box.configure(state="disabled")
        notes_box.pack(fill="x")

    # -- search ----------------------------------------------------------------
    def _build_search(self) -> None:
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=16)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            header, text="Search & Results", font=(FONT, 24, "bold"),
            text_color=TEXT,
        ).pack(side="left")

        self._search_btn = ctk.CTkButton(
            header, text="Search Now", command=self._do_search,
            fg_color=CURRENCY, hover_color="#c73e4d",
            font=(FONT, 13, "bold"), width=120,
        )
        self._search_btn.pack(side="right")

        loc_frame = ctk.CTkFrame(header, fg_color="transparent")
        loc_frame.pack(side="right", padx=12)
        locs = self.settings.get("locations", {})
        active_locs = [k.replace("_", " ").title() for k, v in locs.items() if v]
        ctk.CTkLabel(
            loc_frame, text=f"Active: {', '.join(active_locs) or 'None'}",
            font=(FONT, 11), text_color=SUBTEXT,
        ).pack()

        self._results_scroll = ctk.CTkScrollableFrame(
            frame, fg_color=SECONDARY, corner_radius=8,
        )
        self._results_scroll.pack(fill="both", expand=True)
        self._refresh_results()

    def _do_search(self) -> None:
        self._search_btn.configure(state="disabled", text="Searching...")
        self._set_status("Searching job boards...")

        def search_thread() -> None:
            try:
                kws = self.settings.get("keywords", [])
                locs = self.settings.get("locations", {})
                results = run_all(kws, locs)
                new_rows = add_jobs(results)
                self.after(0, self._search_done, new_rows)
            except Exception as exc:
                self.after(0, self._search_done, 0, str(exc))

        threading.Thread(target=search_thread, daemon=True).start()

    def _search_done(self, new_count: int, error: str = "") -> None:
        self._search_btn.configure(state="normal", text="Search Now")
        if error:
            self._set_status(f"Search error: {error}")
        else:
            self._set_status(f"Found {new_count} new jobs")
        self._refresh_results()

    def _refresh_results(self) -> None:
        for w in self._results_scroll.winfo_children():
            w.destroy()
        jobs = get_all_jobs()
        if not jobs:
            ctk.CTkLabel(
                self._results_scroll, text="No jobs yet. Run a search!",
                font=(FONT, 13), text_color=SUBTEXT,
            ).pack(pady=40)
            return

        cols = ["Status", "Title", "Company", "Location", "Source", "Match", "Date"]
        widths = [80, 280, 150, 130, 110, 60, 100]
        header_row = ctk.CTkFrame(
            self._results_scroll, fg_color=ACCENT, corner_radius=4,
        )
        header_row.pack(fill="x", pady=(0, 4))
        for col, w in zip(cols, widths):
            ctk.CTkLabel(
                header_row, text=col, width=w, anchor="w",
                font=(FONT, 11, "bold"), text_color=TEXT,
            ).pack(side="left", padx=4, pady=4)

        for job in jobs:
            score = job.get("match_score", 0) or 0
            status = job.get("status", "New")
            row_bg = SECONDARY if status == "New" else PRIMARY
            row = ctk.CTkFrame(
                self._results_scroll, fg_color=row_bg, corner_radius=2,
            )
            row.pack(fill="x", pady=1)
            values = [
                status, job.get("title", ""), job.get("company", ""),
                job.get("location", ""), job.get("source", ""),
                f"{score}%", job.get("date_found", ""),
            ]
            for val, w in zip(values, widths):
                ctk.CTkLabel(
                    row, text=val[:60], width=w, anchor="w",
                    font=(FONT, 11), text_color=TEXT,
                ).pack(side="left", padx=4, pady=2)

    # -- keywords --------------------------------------------------------------
    def _build_keywords(self) -> None:
        frame = ctk.CTkScrollableFrame(
            self._content_frame, fg_color="transparent",
        )
        frame.pack(fill="both", expand=True, padx=24, pady=16)

        ctk.CTkLabel(
            frame, text="Keywords", font=(FONT, 24, "bold"), text_color=TEXT,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            frame, text="Add keywords used to match jobs against your resume.",
            font=(FONT, 11), text_color=SUBTEXT,
        ).pack(anchor="w", pady=(0, 16))

        input_row = ctk.CTkFrame(frame, fg_color="transparent")
        input_row.pack(fill="x", pady=(0, 16))

        self._kw_entry = ctk.CTkEntry(
            input_row, placeholder_text="e.g. network administration",
            font=(FONT, 13), fg_color=SECONDARY, border_color=ACCENT,
            width=300,
        )
        self._kw_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            input_row, text="Add", command=self._add_keyword,
            fg_color=ACCENT, font=(FONT, 12), width=70,
        ).pack(side="left", padx=4)

        from job_agent.resume_parser import extract_keywords
        ctk.CTkButton(
            input_row, text="Import from Resume", width=150,
            command=lambda: self._import_keywords(extract_keywords()),
            fg_color="transparent", border_width=1, border_color=ACCENT,
            font=(FONT, 12), text_color=TEXT,
        ).pack(side="left", padx=4)

        self._kw_container = ctk.CTkFrame(frame, fg_color="transparent")
        self._kw_container.pack(fill="x")
        self._refresh_keywords()

    def _add_keyword(self) -> None:
        kw = self._kw_entry.get().strip().lower()
        if not kw:
            return
        existing = self.settings.get("keywords", [])
        if kw not in existing:
            existing.append(kw)
            save_settings(self.settings)
        self._kw_entry.delete(0, "end")
        self._refresh_keywords()

    def _import_keywords(self, kws: list[str]) -> None:
        existing = self.settings.get("keywords", [])
        changed = False
        for kw in kws:
            if kw.lower() not in existing:
                existing.append(kw.lower())
                changed = True
        if changed:
            save_settings(self.settings)
        self._refresh_keywords()

    def _remove_keyword(self, kw: str) -> None:
        existing = self.settings.get("keywords", [])
        if kw in existing:
            existing.remove(kw)
            save_settings(self.settings)
        self._refresh_keywords()

    def _refresh_keywords(self) -> None:
        for w in self._kw_container.winfo_children():
            w.destroy()
        for kw in self.settings.get("keywords", []):
            chip = ctk.CTkFrame(
                self._kw_container, fg_color=ACCENT, corner_radius=14,
            )
            chip.pack(side="left", padx=4, pady=4)
            ctk.CTkLabel(
                chip, text=kw, font=(FONT, 11), text_color=TEXT,
            ).pack(side="left", padx=(10, 2), pady=4)
            ctk.CTkButton(
                chip, text="X", width=20, height=20,
                fg_color="transparent", text_color=CURRENCY,
                hover_color=SECONDARY, font=(FONT, 10, "bold"),
                command=lambda k=kw: self._remove_keyword(k),
            ).pack(side="right", padx=(0, 4))

    # -- resume ----------------------------------------------------------------
    def _build_resume(self) -> None:
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=16)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="My Resume", font=(FONT, 24, "bold"), text_color=TEXT,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        from job_agent.resume_parser import load_resume_text, extract_keywords, get_language_profile

        text_frame = ctk.CTkFrame(frame, fg_color=SECONDARY, corner_radius=8)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(
            text_frame, text="Resume Text", font=(FONT, 14, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=12, pady=(8, 4))
        txt = ctk.CTkTextbox(
            text_frame, fg_color=PRIMARY, text_color=TEXT, font=(FONT, 11),
            wrap="word",
        )
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("0.0", load_resume_text())
        txt.configure(state="disabled")

        skills_frame = ctk.CTkFrame(frame, fg_color=SECONDARY, corner_radius=8)
        skills_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(
            skills_frame, text="Extracted Skills", font=(FONT, 14, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=12, pady=(8, 4))

        skills_inner = ctk.CTkScrollableFrame(
            skills_frame, fg_color="transparent", corner_radius=0,
        )
        skills_inner.pack(fill="both", expand=True, padx=8, pady=8)

        for kw in extract_keywords():
            ctk.CTkLabel(
                skills_inner, text=f"  {kw}", anchor="w",
                font=(FONT, 11), text_color=TEXT,
                fg_color=ACCENT, corner_radius=4,
            ).pack(fill="x", pady=1, ipady=2)

        ctk.CTkLabel(
            skills_frame, text="Languages", font=(FONT, 14, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=12, pady=(12, 4))
        for lang, level in get_language_profile().items():
            ctk.CTkLabel(
                skills_frame, text=f"{lang}: {level}",
                font=(FONT, 11), text_color=SUBTEXT,
            ).pack(anchor="w", padx=16, pady=1)

    # -- approved --------------------------------------------------------------
    def _build_approved(self) -> None:
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=16)

        ctk.CTkLabel(
            frame, text="Approved Jobs", font=(FONT, 24, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", pady=(0, 12))

        scroll = ctk.CTkScrollableFrame(frame, fg_color=SECONDARY, corner_radius=8)
        scroll.pack(fill="both", expand=True)

        jobs = get_all_jobs()
        approved = [j for j in jobs if j.get("status") == "Approved"]
        if not approved:
            ctk.CTkLabel(
                scroll, text="No approved jobs yet.",
                font=(FONT, 13), text_color=SUBTEXT,
            ).pack(pady=40)
            return

        for job in approved:
            card = ctk.CTkFrame(scroll, fg_color=PRIMARY, corner_radius=6)
            card.pack(fill="x", pady=3, padx=4, ipady=6)
            ctk.CTkLabel(
                card, text=job.get("title", ""),
                font=(FONT, 13, "bold"), text_color=TEXT,
            ).pack(anchor="w", padx=12, pady=(4, 0))
            ctk.CTkLabel(
                card, text=f"{job.get('company', '')} — {job.get('location', '')}",
                font=(FONT, 11), text_color=SUBTEXT,
            ).pack(anchor="w", padx=12)

    # -- export ----------------------------------------------------------------
    def _build_export(self) -> None:
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=16)

        ctk.CTkLabel(
            frame, text="Export", font=(FONT, 24, "bold"), text_color=TEXT,
        ).pack(anchor="w", pady=(0, 16))

        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.pack(fill="x")

        export_options = [
            ("Export to PDF", "Generate a PDF report of all jobs", self._export_pdf),
            ("Full Report", "Detailed report with match scores", self._export_report),
            ("Print Preview", "Open print-friendly view", self._export_print),
        ]
        for title, desc, cmd in export_options:
            card = ctk.CTkFrame(cards_frame, fg_color=SECONDARY, corner_radius=8)
            card.pack(side="left", fill="x", expand=True, padx=6, ipady=12)
            ctk.CTkLabel(
                card, text=title, font=(FONT, 15, "bold"), text_color=TEXT,
            ).pack(pady=(16, 4))
            ctk.CTkLabel(
                card, text=desc, font=(FONT, 11), text_color=SUBTEXT,
            ).pack(pady=(0, 12))
            ctk.CTkButton(
                card, text="Open", command=cmd,
                fg_color=ACCENT, font=(FONT, 12), width=100,
            ).pack(pady=(0, 12))

    def _export_pdf(self) -> None:
        append_note("Exported jobs to PDF")
        self._set_status("PDF export placeholder")

    def _export_report(self) -> None:
        append_note("Exported full report")
        self._set_status("Full report export placeholder")

    def _export_print(self) -> None:
        append_note("Opened print preview")
        self._set_status("Print preview placeholder")

    # -- settings --------------------------------------------------------------
    def _build_settings(self) -> None:
        frame = ctk.CTkScrollableFrame(
            self._content_frame, fg_color="transparent",
        )
        frame.pack(fill="both", expand=True, padx=24, pady=16)

        ctk.CTkLabel(
            frame, text="Settings", font=(FONT, 24, "bold"), text_color=TEXT,
        ).pack(anchor="w", pady=(0, 16))

        # Gmail block
        gmail_frame = ctk.CTkFrame(frame, fg_color=SECONDARY, corner_radius=8)
        gmail_frame.pack(fill="x", pady=(0, 16), ipady=8)
        ctk.CTkLabel(
            gmail_frame, text="Gmail Notifications", font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(8, 8))

        ctk.CTkLabel(gmail_frame, text="Email:", text_color=SUBTEXT, font=(FONT, 12)).pack(anchor="w", padx=16)
        email_entry = ctk.CTkEntry(
            gmail_frame, font=(FONT, 13), fg_color=PRIMARY, border_color=ACCENT,
        )
        email_entry.insert(0, self.settings.get("gmail_user", ""))
        email_entry.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(gmail_frame, text="App Password:", text_color=SUBTEXT, font=(FONT, 12)).pack(anchor="w", padx=16)
        pass_entry = ctk.CTkEntry(
            gmail_frame, font=(FONT, 13), fg_color=PRIMARY, border_color=ACCENT,
            show="*",
        )
        pass_entry.insert(0, self.settings.get("gmail_pass", ""))
        pass_entry.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            gmail_frame, text="Use a Gmail App Password (not your regular password)",
            font=(FONT, 10), text_color=SUBTEXT,
        ).pack(anchor="w", padx=16)

        # Locations
        loc_frame = ctk.CTkFrame(frame, fg_color=SECONDARY, corner_radius=8)
        loc_frame.pack(fill="x", pady=(0, 16), ipady=8)
        ctk.CTkLabel(
            loc_frame, text="Job Locations", font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(8, 8))

        loc_vars: dict[str, ctk.BooleanVar] = {}
        for loc_key, loc_label in [
            ("global_remote", "Global Remote"),
            ("arabic_remote", "Arabic Remote"),
            ("mexico", "Mexico"),
        ]:
            var = ctk.BooleanVar(value=self.settings.get("locations", {}).get(loc_key, True))
            loc_vars[loc_key] = var
            ctk.CTkCheckBox(
                loc_frame, text=loc_label, variable=var,
                font=(FONT, 12), text_color=TEXT,
                fg_color=ACCENT,
            ).pack(anchor="w", padx=24, pady=2)

        # Languages
        lang_frame = ctk.CTkFrame(frame, fg_color=SECONDARY, corner_radius=8)
        lang_frame.pack(fill="x", pady=(0, 16), ipady=8)
        ctk.CTkLabel(
            lang_frame, text="Language Filter", font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(8, 8))

        lang_vars: dict[str, ctk.BooleanVar] = {}
        for lang_key, lang_label in [
            ("english", "English"),
            ("arabic", "Arabic"),
            ("french", "French"),
            ("spanish", "Spanish"),
        ]:
            var = ctk.BooleanVar(value=self.settings.get("languages", {}).get(lang_key, True))
            lang_vars[lang_key] = var
            ctk.CTkCheckBox(
                lang_frame, text=lang_label, variable=var,
                font=(FONT, 12), text_color=TEXT,
                fg_color=ACCENT,
            ).pack(anchor="w", padx=24, pady=2)

        # Match threshold
        thresh_frame = ctk.CTkFrame(frame, fg_color=SECONDARY, corner_radius=8)
        thresh_frame.pack(fill="x", pady=(0, 16), ipady=8)
        ctk.CTkLabel(
            thresh_frame, text="Minimum Match Score", font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(8, 4))

        score_var = ctk.IntVar(value=self.settings.get("min_match_score", 30))
        score_slider = ctk.CTkSlider(
            thresh_frame, from_=0, to=100, variable=score_var,
            number_of_steps=100, fg_color=PRIMARY,
            progress_color=CURRENCY, button_color=CURRENCY,
        )
        score_slider.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            thresh_frame, textvariable=score_var,
            font=(FONT, 20, "bold"), text_color=CURRENCY,
        ).pack(anchor="e", padx=16)

        # Schedule
        sched_frame = ctk.CTkFrame(frame, fg_color=SECONDARY, corner_radius=8)
        sched_frame.pack(fill="x", pady=(0, 16), ipady=8)
        ctk.CTkLabel(
            sched_frame, text="Daily Schedule", font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(8, 8))

        sched_row = ctk.CTkFrame(sched_frame, fg_color="transparent")
        sched_row.pack(anchor="w", padx=24, pady=(0, 8))
        ctk.CTkLabel(
            sched_row, text="Run at:", font=(FONT, 12), text_color=SUBTEXT,
        ).pack(side="left")
        time_val = self.settings.get("schedule_time", "08:00")
        time_entry = ctk.CTkEntry(
            sched_row, width=80, font=(FONT, 13),
            fg_color=PRIMARY, border_color=ACCENT,
        )
        time_entry.insert(0, time_val)
        time_entry.pack(side="left", padx=8)
        ctk.CTkLabel(
            sched_row, text="(24h format, e.g. 08:00)",
            font=(FONT, 10), text_color=SUBTEXT,
        ).pack(side="left")

        def save_all_settings() -> None:
            self.settings["gmail_user"] = email_entry.get()
            self.settings["gmail_pass"] = pass_entry.get()
            self.settings["schedule_time"] = time_entry.get()
            locs = {}
            for k, v in loc_vars.items():
                locs[k] = v.get()
            self.settings["locations"] = locs
            langs = {}
            for k, v in lang_vars.items():
                langs[k] = v.get()
            self.settings["languages"] = langs
            self.settings["min_match_score"] = score_var.get()
            save_settings(self.settings)
            self._set_status("Settings saved")

        ctk.CTkButton(
            frame, text="Save All Settings", command=save_all_settings,
            fg_color=CURRENCY, hover_color="#c73e4d",
            font=(FONT, 13, "bold"),
        ).pack(anchor="w", pady=20)


def run() -> None:
    app = JobAgentApp()
    app.mainloop()