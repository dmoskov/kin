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
import logging
import os
import re
import time
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_from_directory, session

from database.connection import init_db
from database.repository import TreeRepository
from import_export.json_io import (
    _article_to_dict,
    _citation_to_dict,
    _person_to_dict,
    _rel_to_dict,
    _source_to_dict,
    _union_to_dict,
)
from storage import photo_storage

logger = logging.getLogger(__name__)


# ── Paths ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = str(PROJECT_ROOT / "web")
PRIVATE_DIR = PROJECT_ROOT / "private"

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# Upload size limits. MAX_CONTENT_LENGTH is enforced by Flask at the WSGI
# layer (before we see the request). MAX_PHOTO_BYTES / MAX_DOC_BYTES are
# enforced explicitly inside the upload handlers so we can return a clean
# JSON error with a helpful message.
MAX_PHOTO_BYTES = int(os.environ.get("MAX_PHOTO_BYTES", 8 * 1024 * 1024))  # 8 MB
MAX_DOC_BYTES = int(os.environ.get("MAX_DOC_BYTES", 50 * 1024 * 1024))  # 50 MB
app.config["MAX_CONTENT_LENGTH"] = max(MAX_PHOTO_BYTES, MAX_DOC_BYTES) + 1024 * 1024

# Comma-separated list of Gmail addresses that may write to the tree.
# Anyone not on this list can view but not edit.
# Example: EDITORS=alice@gmail.com,bob@gmail.com
EDITORS: set[str] = {
    e.strip().lower() for e in os.environ.get("EDITORS", "").split(",") if e.strip()
}

ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@app.errorhandler(413)
def _handle_too_large(_err):
    """Return JSON (not HTML) for oversize uploads."""
    return jsonify(
        {
            "error": "File is too large",
            "code": "too_large",
        }
    ), 413


@app.before_request
def _ensure_db():
    """Ensure the database is initialized on first request."""
    if not getattr(app, "_db_initialized", False):
        init_db()
        app._db_initialized = True


# ── Auth helpers ───────────────────────────────────────────────────────


def _editors_configured() -> bool:
    """Return True if any editor access control is configured (env or DB)."""
    if EDITORS:
        return True
    try:
        from database.connection import get_connection
        from database.repository import _fetchone

        conn = get_connection()
        try:
            row = _fetchone(conn, "SELECT 1 FROM tree_editors LIMIT 1")
            return row is not None
        finally:
            conn.close()
    except Exception:
        return False


def require_login(f):
    """Reject unauthenticated users when Google Sign-In is configured.

    If GOOGLE_CLIENT_ID is not set, the original open-access behaviour is
    preserved so existing deployments are not broken.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        if os.environ.get("GOOGLE_CLIENT_ID") and "person_id" not in session:
            return jsonify({"error": "login required", "code": "unauthorized"}), 401
        return f(*args, **kwargs)

    return wrapper


def require_editor(f):
    """Reject non-editors when an EDITORS list or tree_editors are configured.

    If neither is set, the original open-access behaviour is preserved
    so existing deployments are not broken.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        if _editors_configured() and not session.get("is_editor"):
            return jsonify({"error": "editor access required", "code": "forbidden"}), 403
        return f(*args, **kwargs)

    return wrapper


# ── File helpers (shared by blueprint modules) ────────────────────────


def _sanitize_filename(name: str) -> str:
    """Turn a filename into a safe slug with timestamp prefix.

    Hardened against:
      - path traversal (``../``)
      - NUL bytes
      - empty stems after slugification (falls back to ``upload``)
      - mixed-case / non-ASCII extensions
    """
    # Strip any directory components an attacker may have embedded.
    raw = Path(name.replace("\x00", "")).name
    stem = Path(raw).stem
    ext = Path(raw).suffix.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")[:80]
    if not slug:
        slug = "upload"
    ts = int(time.time())
    return f"{ts}-{slug}{ext}"


def _measure_file_size(file_storage) -> int:
    """Return the byte size of a Werkzeug ``FileStorage`` without reading
    the whole thing into memory. Leaves the stream positioned at the start.
    """
    stream = file_storage.stream
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
    finally:
        stream.seek(0)
    return size


def _atomic_save(file_storage, dest: Path) -> None:
    """Save a FileStorage to ``dest`` atomically via a ``.part`` tempfile.

    On success, ``dest`` exists and contains the full payload. On failure,
    the partial file is cleaned up and ``dest`` is not created.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        file_storage.save(str(tmp))
        os.replace(str(tmp), str(dest))
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _looks_like_image(path: Path, ext: str) -> bool:
    """Return True if the file's magic bytes match the declared extension.

    Implemented by inspecting the header bytes directly so we don't depend
    on ``imghdr`` (removed in Python 3.13+).
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return False

    if ext in (".jpg", ".jpeg"):
        # JPEGs begin with FF D8 FF. All variants (JFIF, Exif, raw) share
        # this prefix.
        return head[:3] == b"\xff\xd8\xff"
    if ext == ".png":
        return head[:8] == b"\x89PNG\r\n\x1a\n"
    if ext == ".gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if ext == ".webp":
        # WebP is RIFF<size>WEBP in the first 12 bytes.
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def _looks_like_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(5) == b"%PDF-"
    except OSError:
        return False


def _get_google_client_id() -> str | None:
    """Get the Google Client ID from env or config file."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if client_id:
        return client_id
    # Fall back to family-config.json
    for candidate in [
        PRIVATE_DIR / "config" / "family-config.json",
        Path(WEB_DIR) / "family-config.json",
    ]:
        if candidate.exists():
            config = json.loads(candidate.read_text())
            if config.get("googleClientId"):
                return config["googleClientId"]
    return None


# ── Core routes ────────────────────────────────────────────────────────


@app.before_request
def _enforce_login():
    """Require login for data endpoints when Google Sign-In is configured."""
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        return  # No auth configured — open access
    path = request.path
    # Always allow: health check, auth endpoints, config, static assets, index
    if (
        path == "/healthz"
        or path.startswith("/api/auth/")
        or path == "/api/config"
        or path in ("/", "")
        or path.startswith("/js/")
        or path.startswith("/dist/")
        or path.startswith("/icons/")
        or path.endswith(".css")
        or path.endswith(".svg")
        or path.endswith(".png")
        or path.endswith(".ico")
        or path.endswith(".js")
        or path.endswith(".woff2")
    ):
        return  # Allow through
    # Protect API, photos, and documents
    if (
        path.startswith("/api/") or path.startswith("/photos/") or path.startswith("/documents/")
    ) and "person_id" not in session:
        return jsonify({"error": "login required", "code": "unauthorized"}), 401


@app.route("/healthz")
def healthz():
    """Unauthenticated liveness probe for deploys/monitoring."""
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    # Serve the minified single-file bundle when it exists (produced by
    # scripts/build_js.sh); otherwise serve the ES modules directly for dev.
    html = (Path(WEB_DIR) / "index.html").read_text()
    if (Path(WEB_DIR) / "dist" / "app.min.js").exists():
        html = html.replace(
            '<script type="module" src="/js/99-main.js"></script>',
            '<script type="module" src="/dist/app.min.js"></script>',
        )
    return Response(html, mimetype="text/html")


@app.errorhandler(404)
def spa_fallback(e):
    """Serve index.html for client-side routes; return JSON 404 for API/asset paths."""
    path = request.path
    # Treat paths with a file extension as static assets, not client-side routes.
    filename = path.rsplit("/", 1)[-1]
    has_extension = "." in filename
    is_asset = (
        has_extension
        or path.startswith("/api/")
        or path.startswith("/documents/")
        or (path.startswith("/photos/") and not path.startswith("/photos/view/"))
    )
    if is_asset:
        return jsonify({"error": "not found", "code": "not_found"}), 404
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/api/config")
def api_config():
    """Return the family configuration (theme, heritage, fonts, etc.).

    Looks for config in this order:
      1. private/config/family-config.json  (personal, gitignored)
      2. web/family-config.json             (legacy / dev override)
      3. Built-in defaults
    """
    editors_enabled = _editors_configured()
    editors_misconfigured = editors_enabled and not _get_google_client_id()
    admin_person_id = os.environ.get("ADMIN_PERSON_ID", "")

    for candidate in [
        PRIVATE_DIR / "config" / "family-config.json",
        Path(WEB_DIR) / "family-config.json",
    ]:
        if candidate.exists():
            config = json.loads(candidate.read_text())
            config["editorsEnabled"] = editors_enabled
            config["editorsMisconfigured"] = editors_misconfigured
            if admin_person_id:
                config["adminPersonId"] = admin_person_id
            return jsonify(config)
    # Sensible defaults when no config file exists
    return jsonify(
        {
            "familyName": "Family Tree",
            "subtitle": "",
            "headerFont": "'Inter', sans-serif",
            "bodyFont": "'Inter', sans-serif",
            "heritage": [],
            "palette": {},
            "timelinePhotos": True,
            "heritageLabels": False,
            "editorsEnabled": editors_enabled,
            "editorsMisconfigured": editors_misconfigured,
            **({"adminPersonId": admin_person_id} if admin_person_id else {}),
        }
    )


@app.route("/photos/<path:filename>")
def serve_photo(filename):
    """Serve photos from S3 (if configured) or local disk."""
    data = photo_storage.get(filename)
    if data is None:
        abort(404)
    import mimetypes

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        data,
        content_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _build_events_with_ids(repo, tree):
    """Build event dicts that include the database row id."""
    conn = repo._conn()
    try:
        from database.repository import _fetchall

        rows = _fetchall(
            conn,
            "SELECT id, person_id, event_type, date, end_date, place, description, source, date_circa FROM events",
        )
        result = []
        for row in rows:
            d = {"id": row["id"], "person_id": row["person_id"], "event_type": row["event_type"]}
            for key in ("date", "end_date", "place", "source"):
                val = row.get(key)
                if val is not None:
                    d[key] = val
            if row.get("description"):
                d["description"] = row["description"]
            if row.get("date_circa"):
                d["date_circa"] = True
            result.append(d)
        return result
    finally:
        conn.close()


@app.route("/api/data")
def api_data():
    """Return the full family tree as JSON (read from DB on each request)."""
    repo = TreeRepository()
    tree = repo.load_tree()
    all_photos = repo.list_all_photos()
    photos_list = []
    for p in all_photos:
        photos_list.append(
            {
                "id": p["id"],
                "file_path": p["file_path"],
                "date": p.get("date"),
                "date_circa": bool(p.get("date_circa")),
                "place": p.get("place"),
                "photo_type": p.get("photo_type", "photo"),
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "tagged_people": [
                    {
                        "person_id": tp["person_id"],
                        "is_profile": bool(tp.get("is_profile")),
                        "caption": tp.get("caption", ""),
                        "given_name": tp.get("given_name", ""),
                        "surname": tp.get("surname", ""),
                        "crop_x": tp.get("crop_x"),
                        "crop_y": tp.get("crop_y"),
                        "crop_w": tp.get("crop_w"),
                        "crop_h": tp.get("crop_h"),
                    }
                    for tp in p.get("tagged_people", [])
                ],
                "face_regions": [
                    {
                        "id": fr["id"],
                        "person_id": fr["person_id"],
                        "x": fr["x"],
                        "y": fr["y"],
                        "w": fr["w"],
                        "h": fr["h"],
                        "given_name": fr.get("given_name", ""),
                        "surname": fr.get("surname", ""),
                    }
                    for fr in p.get("face_regions", [])
                ],
            }
        )
    article_person_map: dict[str, list[str]] = {}
    for pid, aids in tree.person_article_links.items():
        for aid in aids:
            article_person_map.setdefault(aid, []).append(pid)

    events_with_ids = _build_events_with_ids(repo, tree)
    data = {
        "people": [_person_to_dict(p) for p in tree.people.values()],
        "relationships": [_rel_to_dict(r) for r in tree.relationships],
        "unions": [_union_to_dict(u) for u in tree.unions],
        "events": events_with_ids,
        "sources": [_source_to_dict(s) for s in tree.sources.values()],
        "citations": [_citation_to_dict(c) for c in tree.citations],
        "articles": [
            _article_to_dict(a, article_person_map.get(a.id)) for a in tree.articles.values()
        ],
        "photos": photos_list,
    }
    return jsonify(data)


@app.route("/api/photos")
def api_photos():
    """Return rich photo objects from the photos table, with tagged people.

    Falls back to a flat path list if the photos table is empty (pre-migration).
    """
    repo = TreeRepository()
    photos = repo.list_all_photos()
    if photos:
        result = []
        for p in photos:
            obj = {
                "id": p["id"],
                "file_path": p["file_path"],
                "date": p.get("date"),
                "date_circa": bool(p.get("date_circa")),
                "place": p.get("place"),
                "photo_type": p.get("photo_type", "photo"),
                "tagged_people": [
                    {
                        "person_id": tp["person_id"],
                        "is_profile": bool(tp.get("is_profile")),
                        "caption": tp.get("caption", ""),
                        "given_name": tp.get("given_name", ""),
                        "surname": tp.get("surname", ""),
                    }
                    for tp in p.get("tagged_people", [])
                ],
            }
            result.append(obj)
        return jsonify(result)
    names = photo_storage.list_all()
    return jsonify([f"photos/{n}" for n in names])


# ── Register blueprints ───────────────────────────────────────────────

from routes import ALL_BLUEPRINTS  # noqa: E402  (imported here so app is defined first)

for bp in ALL_BLUEPRINTS:
    app.register_blueprint(bp)


# ── Standalone dev server ──────────────────────────────────────────────


def serve(port: int = 8000) -> None:
    """Start the Flask dev server (for local use only)."""
    if not Path(WEB_DIR).is_dir():
        print(f"Error: web directory not found at {WEB_DIR}")
        return

    print("\n  Family Tree Dashboard")
    print(f"  http://localhost:{port}")
    print(f"  API: http://localhost:{port}/api/data")
    print("\n  Press Ctrl+C to stop.\n")

    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Family Tree web server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()
    serve(args.port)
