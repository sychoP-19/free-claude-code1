"""JobAgent Pro — Flask web backend."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from job_agent.matcher import match_job, send_email_notification
from job_agent.resume_parser import extract_keywords, get_language_profile, load_resume_text
from job_agent.scrapers.orchestrator import run_all
from job_agent.storage import (
    add_jobs,
    append_note,
    get_all_jobs,
    get_notes,
    load_settings,
    save_settings,
    update_job_status,
)

app = Flask(__name__, static_folder="static", static_url_path="")
HERE = Path(__file__).parent


@app.route("/")
def index() -> Response:
    return send_from_directory(HERE / "templates", "index.html")


@app.route("/<path:path>")
def static_files(path: str) -> Response:
    if (HERE / "static" / path).exists():
        return send_from_directory(HERE / "static", path)
    return send_from_directory(HERE / "templates", "index.html")


@app.route("/api/jobs", methods=["GET"])
def api_get_jobs() -> Response:
    jobs = get_all_jobs()
    return jsonify(jobs)


@app.route("/api/jobs", methods=["POST"])
def api_update_job() -> Response:
    data = request.get_json(force=True)
    url = data.get("url", "")
    status = data.get("status", "")
    if url and status:
        update_job_status(url, status)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "url and status required"}), 400


@app.route("/api/search", methods=["POST"])
def api_search() -> Response:
    data = request.get_json(force=True) or {}
    keywords = data.get("keywords", load_settings().get("keywords", []))
    locations = data.get("locations", load_settings().get("locations", {}))
    results = run_all(keywords, locations)
    new_count = add_jobs(results)
    return jsonify({"ok": True, "new_count": new_count, "total": len(results)})


@app.route("/api/search/preview", methods=["POST"])
def api_search_preview() -> Response:
    """Run search and return results without saving to Excel."""
    data = request.get_json(force=True) or {}
    keywords = data.get("keywords", load_settings().get("keywords", []))
    locations = data.get("locations", load_settings().get("locations", {}))
    results = run_all(keywords, locations)
    return jsonify({"ok": True, "jobs": results})


@app.route("/api/settings", methods=["GET"])
def api_get_settings() -> Response:
    return jsonify(load_settings())


@app.route("/api/settings", methods=["POST"])
def api_save_settings() -> Response:
    data = request.get_json(force=True)
    save_settings(data)
    return jsonify({"ok": True})


@app.route("/api/resume", methods=["GET"])
def api_get_resume() -> Response:
    return jsonify({
        "text": load_resume_text(),
        "keywords": extract_keywords(),
        "languages": get_language_profile(),
    })


@app.route("/api/resume/keywords", methods=["POST"])
def api_import_keywords() -> Response:
    settings = load_settings()
    existing = settings.get("keywords", [])
    imported = [kw.lower() for kw in extract_keywords() if kw.lower() not in existing]
    settings["keywords"] = existing + imported
    save_settings(settings)
    return jsonify({"ok": True, "imported": imported})


@app.route("/api/notes", methods=["GET"])
def api_get_notes() -> Response:
    return jsonify({"text": get_notes()})


@app.route("/api/notes", methods=["POST"])
def api_add_note() -> Response:
    data = request.get_json(force=True)
    text = data.get("text", "")
    if text:
        append_note(text)
    return jsonify({"ok": True})


@app.route("/api/email/test", methods=["POST"])
def api_test_email() -> Response:
    data = request.get_json(force=True)
    user = data.get("user", "")
    pwd = data.get("pass", "")
    sent = send_email_notification(user, pwd, user, 0, 0)
    return jsonify({"ok": sent})


def main() -> None:
    import webbrowser

    port = int(load_settings().get("web_port", 8080))
    webbrowser.open(f"http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()