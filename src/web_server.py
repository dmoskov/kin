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

from flask import Flask, jsonify, request, send_from_directory, abort

from database.connection import get_connection, init_db
from database.repository import TreeRepository
from import_export.json_io import (
    _citation_to_dict,
    _event_to_dict,
    _person_to_dict,
    _rel_to_dict,
    _source_to_dict,
    _union_to_dict,
)


# ── App factory ────────────────────────────────────────────────────────

WEB_DIR = str(Path(__file__).resolve().parent.parent / "web")

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

    Reads from web/family-config.json.  Falls back to minimal defaults
    so the dashboard always works even without a config file.
    """
    config_path = Path(WEB_DIR) / "family-config.json"
    if config_path.exists():
        return jsonify(json.loads(config_path.read_text()))
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


@app.route("/api/photos")
def api_photos():
    """Return a list of all photo files in web/photos/."""
    photos_dir = Path(WEB_DIR) / "photos"
    if not photos_dir.is_dir():
        return jsonify([])
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    photos = sorted(
        f"photos/{f.name}"
        for f in photos_dir.iterdir()
        if f.suffix.lower() in exts
    )
    return jsonify(photos)


@app.route("/api/people/<person_id>/photos", methods=["POST"])
def api_add_photos(person_id):
    """Add photos to a person. Body: {"photo_paths": ["photos/foo.jpg"]}"""
    body = request.get_json(force=True)
    new_paths = body.get("photo_paths", [])
    if not new_paths:
        return jsonify({"error": "photo_paths required"}), 400

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT photo_paths FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "person not found"}), 404

        existing = json.loads(row["photo_paths"] or "[]")
        merged = list(existing)
        for p in new_paths:
            if p not in merged:
                merged.append(p)

        conn.execute(
            "UPDATE people SET photo_paths = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(merged), person_id),
        )
        conn.commit()
        return jsonify({"photo_paths": merged})
    finally:
        conn.close()


@app.route("/api/people/<person_id>/photos", methods=["DELETE"])
def api_remove_photo(person_id):
    """Remove a photo from a person. Body: {"photo_path": "photos/foo.jpg"}"""
    body = request.get_json(force=True)
    photo_path = body.get("photo_path", "")
    if not photo_path:
        return jsonify({"error": "photo_path required"}), 400

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT photo_paths FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "person not found"}), 404

        existing = json.loads(row["photo_paths"] or "[]")
        updated = [p for p in existing if p != photo_path]

        conn.execute(
            "UPDATE people SET photo_paths = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(updated), person_id),
        )
        conn.commit()
        return jsonify({"photo_paths": updated})
    finally:
        conn.close()


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
