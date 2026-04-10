"""Web server for the family tree dashboard.

Flask app that serves static files from web/ and provides API endpoints.
Works with both SQLite (local dev) and PostgreSQL (production via DATABASE_URL).

Usage:
    # Local development
    python -m web_server [--port 8000]

    # Production (via gunicorn)
    gunicorn web_server:app --bind 0.0.0.0:8000

    # Via the CLI
    python -m cli serve [--port 8000]
"""

import json
from pathlib import Path

from flask import Flask, jsonify, send_from_directory, abort

from database.connection import init_db
from database.repository import TreeRepository
from import_export.json_io import (
    _citation_to_dict,
    _event_to_dict,
    _person_to_dict,
    _rel_to_dict,
    _source_to_dict,
    _union_to_dict,
)


# ── Paths ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = str(PROJECT_ROOT / "web")
PRIVATE_DIR = PROJECT_ROOT / "private"

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")


@app.before_request
def _ensure_db():
    """Ensure the database is initialized on first request."""
    if not getattr(app, "_db_initialized", False):
        init_db()
        app._db_initialized = True


# ── Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/api/config")
def api_config():
    """Return the family configuration (theme, heritage, fonts, etc.).

    Looks for config in this order:
      1. private/config/family-config.json  (personal, gitignored)
      2. web/family-config.json             (legacy / dev override)
      3. Built-in defaults
    """
    for candidate in [
        PRIVATE_DIR / "config" / "family-config.json",
        Path(WEB_DIR) / "family-config.json",
    ]:
        if candidate.exists():
            return jsonify(json.loads(candidate.read_text()))
    # Sensible defaults when no config file exists
    return jsonify({
        "familyName": "Family Tree",
        "subtitle": "",
        "headerFont": "'Inter', sans-serif",
        "bodyFont": "'Inter', sans-serif",
        "heritage": [],
        "palette": {},
        "timelinePhotos": True,
        "heritageLabels": False,
    })


@app.route("/photos/<path:filename>")
def serve_photo(filename):
    """Serve photos from private/photos/ or web/photos/ (private takes priority)."""
    private_photos = PRIVATE_DIR / "photos"
    web_photos = Path(WEB_DIR) / "photos"
    for photo_dir in [private_photos, web_photos]:
        if (photo_dir / filename).exists():
            return send_from_directory(str(photo_dir), filename)
    abort(404)


@app.route("/api/data")
def api_data():
    """Return the full family tree as JSON (read from DB on each request)."""
    repo = TreeRepository()
    tree = repo.load_tree()
    data = {
        "people": [_person_to_dict(p) for p in tree.people.values()],
        "relationships": [_rel_to_dict(r) for r in tree.relationships],
        "unions": [_union_to_dict(u) for u in tree.unions],
        "events": [_event_to_dict(e) for e in tree.events],
        "sources": [_source_to_dict(s) for s in tree.sources.values()],
        "citations": [_citation_to_dict(c) for c in tree.citations],
    }
    return jsonify(data)


# ── Standalone dev server ──────────────────────────────────────────────

def serve(port: int = 8000) -> None:
    """Start the Flask dev server (for local use only)."""
    if not Path(WEB_DIR).is_dir():
        print(f"Error: web directory not found at {WEB_DIR}")
        return

    print(f"\n  Family Tree Dashboard")
    print(f"  http://localhost:{port}")
    print(f"  API: http://localhost:{port}/api/data")
    print(f"\n  Press Ctrl+C to stop.\n")

    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Family Tree web server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()
    serve(args.port)
