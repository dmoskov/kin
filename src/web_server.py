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
import uuid
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from functools import wraps

from flask import Flask, jsonify, request, send_from_directory, abort, session

from database.connection import get_connection, init_db
from database.repository import TreeRepository, _execute, _fetchone, _now, _ph
from models.person import Gender, Person
from exif_utils import extract_exif_metadata
from storage import photo_storage

logger = logging.getLogger(__name__)
from import_export.gedcom_import import parse_gedcom
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
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# Upload size limits. MAX_CONTENT_LENGTH is enforced by Flask at the WSGI
# layer (before we see the request). MAX_PHOTO_BYTES / MAX_DOC_BYTES are
# enforced explicitly inside the upload handlers so we can return a clean
# JSON error with a helpful message.
MAX_PHOTO_BYTES = int(os.environ.get("MAX_PHOTO_BYTES", 8 * 1024 * 1024))   # 8 MB
MAX_DOC_BYTES = int(os.environ.get("MAX_DOC_BYTES", 50 * 1024 * 1024))     # 50 MB
app.config["MAX_CONTENT_LENGTH"] = max(MAX_PHOTO_BYTES, MAX_DOC_BYTES) + 1024 * 1024

# Comma-separated list of Gmail addresses that may write to the tree.
# Anyone not on this list can view but not edit.
# Example: EDITORS=alice@gmail.com,bob@gmail.com
EDITORS: set[str] = {
    e.strip().lower()
    for e in os.environ.get("EDITORS", "").split(",")
    if e.strip()
}


@app.errorhandler(413)
def _handle_too_large(_err):
    """Return JSON (not HTML) for oversize uploads."""
    return jsonify({
        "error": "File is too large",
        "code": "too_large",
    }), 413


@app.before_request
def _ensure_db():
    """Ensure the database is initialized on first request."""
    if not getattr(app, "_db_initialized", False):
        init_db()
        app._db_initialized = True


# ── Auth helpers ───────────────────────────────────────────────────────

def require_editor(f):
    """Reject non-editors when an EDITORS list is configured.

    If EDITORS is not set, the original open-access behaviour is preserved
    so existing deployments are not broken.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if EDITORS and not session.get("is_editor"):
            return jsonify({"error": "editor access required", "code": "forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


# ── Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.errorhandler(404)
def spa_fallback(e):
    """Serve index.html for client-side routes; return JSON 404 for API/asset paths."""
    path = request.path
    is_asset = (
        path.startswith("/api/")
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
    editors_enabled = bool(EDITORS)
    editors_misconfigured = editors_enabled and not _get_google_client_id()

    for candidate in [
        PRIVATE_DIR / "config" / "family-config.json",
        Path(WEB_DIR) / "family-config.json",
    ]:
        if candidate.exists():
            config = json.loads(candidate.read_text())
            config["editorsEnabled"] = editors_enabled
            config["editorsMisconfigured"] = editors_misconfigured
            return jsonify(config)
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
        "editorsEnabled": editors_enabled,
        "editorsMisconfigured": editors_misconfigured,
    })


@app.route("/photos/<path:filename>")
def serve_photo(filename):
    """Serve photos from S3 (if configured) or local disk."""
    from flask import Response
    data = photo_storage.get(filename)
    if data is None:
        abort(404)
    import mimetypes
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(data, content_type=content_type,
                    headers={"Cache-Control": "public, max-age=86400"})


@app.route("/api/geocode", methods=["POST"])
def api_geocode():
    """Geocode a list of place strings via Nominatim (with DB cache).

    Body: JSON array of place strings.
    Returns: { coords: {place: [lat, lng]}, pending: N }

    Cached results are returned immediately. Cache misses are resolved
    in a background thread; the client can poll again when pending > 0.
    """
    from geocoder import geocode_places
    places = request.get_json(silent=True) or []
    if not isinstance(places, list):
        return jsonify({"error": "expected a JSON array"}), 400
    coords, pending = geocode_places(places)
    return jsonify({
        "coords": {p: list(c) for p, c in coords.items()},
        "pending": pending,
    })


@app.route("/api/data")
def api_data():
    """Return the full family tree as JSON (read from DB on each request)."""
    repo = TreeRepository()
    tree = repo.load_tree()
    all_photos = repo.list_all_photos()
    photos_list = []
    for p in all_photos:
        photos_list.append({
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
        })
    data = {
        "people": [_person_to_dict(p) for p in tree.people.values()],
        "relationships": [_rel_to_dict(r) for r in tree.relationships],
        "unions": [_union_to_dict(u) for u in tree.unions],
        "events": [_event_to_dict(e) for e in tree.events],
        "sources": [_source_to_dict(s) for s in tree.sources.values()],
        "citations": [_citation_to_dict(c) for c in tree.citations],
        "photos": photos_list,
    }
    return jsonify(data)


# ── Person CRUD ────────────────────────────────────────────────────────
#
# These endpoints let the UI (or any client) add, edit, and delete people
# without needing to hand-craft Python seed scripts. The TreeRepository
# already handles both SQLite (local) and PostgreSQL (production) and
# cascades deletes through FKs on relationships / unions / events /
# citations, so these routes are thin validation + translation layers.


# Fields a client is allowed to provide on create / update. Anything else
# in the request body is ignored silently so older clients don't break.
_PERSON_WRITABLE_FIELDS = {
    "given_name",
    "surname",
    "gender",
    "birth_date",
    "birth_place",
    "death_date",
    "death_place",
    "maiden_name",
    "nicknames",
    "notes",
    "email",
}

# Gender is an enum; accept the string value or fall back to UNKNOWN.
_VALID_GENDERS = {g.value for g in Gender}


def _coerce_person_payload(body: dict, *, partial: bool) -> tuple[dict, str | None, int]:
    """Validate + normalize a person payload.

    Returns ``(normalized, error_message, status_code)``. On success
    ``error_message`` is None and ``status_code`` is 0.

    ``partial=True`` (used by PUT) allows missing fields; ``partial=False``
    (used by POST) requires at least given_name or surname (otherwise the
    resulting card has no label at all).
    """
    if not isinstance(body, dict):
        return {}, "body must be a JSON object", 400

    out: dict = {}
    for key, value in body.items():
        if key not in _PERSON_WRITABLE_FIELDS:
            continue
        # Normalize empty strings to None for optional fields so clients
        # don't need to distinguish "" from missing.
        if key in ("given_name", "surname"):
            if value is None:
                value = ""
            if not isinstance(value, str):
                return {}, f"{key} must be a string", 400
            value = value.strip()
        elif key == "gender":
            if value is None:
                value = Gender.UNKNOWN.value
            if not isinstance(value, str) or value not in _VALID_GENDERS:
                return {}, (
                    f"gender must be one of: {', '.join(sorted(_VALID_GENDERS))}"
                ), 400
        elif key == "nicknames":
            if value is None:
                value = []
            if not isinstance(value, list) or not all(isinstance(n, str) for n in value):
                return {}, "nicknames must be a list of strings", 400
        elif key == "notes":
            if value is None:
                value = ""
            if not isinstance(value, str):
                return {}, "notes must be a string", 400
        else:
            # Optional scalar fields (dates, places, maiden_name, email).
            # Allow empty string → None so clients can clear them.
            if isinstance(value, str):
                value = value.strip() or None
            elif value is not None and not isinstance(value, str):
                return {}, f"{key} must be a string or null", 400
        out[key] = value

    if not partial:
        gn = (out.get("given_name") or "").strip()
        sn = (out.get("surname") or "").strip()
        if not gn and not sn:
            return {}, "given_name or surname is required", 400

    # Basic date sanity check — we accept partial dates (YYYY or YYYY-MM)
    # and full ISO dates, but nothing else.
    for date_field in ("birth_date", "death_date"):
        v = out.get(date_field)
        if v and not re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", v):
            return {}, f"{date_field} must be YYYY, YYYY-MM, or YYYY-MM-DD", 400

    return out, None, 0


@app.route("/api/people", methods=["POST"])
@require_editor
def api_create_person():
    """Create a new person.

    Body: JSON object with at least ``given_name`` or ``surname``. Optional
    fields: ``id`` (auto-generated if omitted), ``gender``, ``birth_date``,
    ``birth_place``, ``death_date``, ``death_place``, ``maiden_name``,
    ``nicknames``, ``notes``, ``email``.

    Returns 201 with the created person on success. Returns 409 if an
    explicit ``id`` already exists, 400 for validation errors.
    """
    body = request.get_json(silent=True) or {}
    fields, err, status = _coerce_person_payload(body, partial=False)
    if err:
        return jsonify({"error": err, "code": "bad_request"}), status

    # ID: accept client-provided for deterministic seeding, otherwise mint
    # a fresh UUID-based slug that won't collide with anything.
    pid = (body.get("id") or "").strip() if isinstance(body.get("id"), str) else ""
    if not pid:
        pid = f"person_{uuid.uuid4().hex[:12]}"

    repo = TreeRepository()
    if repo.get_person(pid) is not None:
        return jsonify({
            "error": f"person id already exists: {pid}",
            "code": "conflict",
        }), 409

    person = Person(
        id=pid,
        given_name=fields.get("given_name", ""),
        surname=fields.get("surname", ""),
        gender=Gender(fields.get("gender", Gender.UNKNOWN.value)),
        birth_date=fields.get("birth_date"),
        birth_place=fields.get("birth_place"),
        death_date=fields.get("death_date"),
        death_place=fields.get("death_place"),
        maiden_name=fields.get("maiden_name"),
        nicknames=fields.get("nicknames", []),
        notes=fields.get("notes", ""),
        email=fields.get("email"),
    )
    repo.save_person(person)
    return jsonify(_person_to_dict(person)), 201


@app.route("/api/people/<person_id>", methods=["PUT", "PATCH"])
@require_editor
def api_update_person(person_id):
    """Update an existing person. Partial updates are supported.

    Body: JSON object with any subset of writable fields. Fields not
    included in the body are left unchanged. Pass an empty string (or
    null) for an optional scalar field to clear it.

    Returns 200 with the updated person on success, 404 if not found.
    """
    body = request.get_json(silent=True) or {}
    fields, err, status = _coerce_person_payload(body, partial=True)
    if err:
        return jsonify({"error": err, "code": "bad_request"}), status

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if person is None:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    # Apply only the fields actually present in the request so callers can
    # PATCH without clobbering other columns. `gender` needs enum coercion.
    for key, value in fields.items():
        if key == "gender":
            person.gender = Gender(value)
        else:
            setattr(person, key, value)

    repo.save_person(person)
    return jsonify(_person_to_dict(person))


@app.route("/api/people/<person_id>", methods=["DELETE"])
@require_editor
def api_delete_person(person_id):
    """Delete a person. Cascades to their relationships, unions, events,
    and citations via FK ON DELETE CASCADE (see schema).

    Returns 204 on success, 404 if the person didn't exist.
    """
    repo = TreeRepository()
    if repo.get_person(person_id) is None:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    # delete_person returns True if a row was actually deleted. We already
    # confirmed existence above, so a False here would indicate a race.
    ok = repo.delete_person(person_id)
    if not ok:
        return jsonify({"error": "delete failed", "code": "server_error"}), 500
    return ("", 204)


@app.route("/api/relationships", methods=["POST"])
@require_editor
def api_create_relationship():
    """Create a parent-child relationship.

    Body: {"parent_id": "...", "child_id": "..."}

    Returns 201 on success, 400 for missing fields, 404 if either person
    doesn't exist.
    """
    from models.relationship import Relationship, RelationshipType
    body = request.get_json(silent=True) or {}
    parent_id = (body.get("parent_id") or "").strip()
    child_id = (body.get("child_id") or "").strip()
    if not parent_id or not child_id:
        return jsonify({"error": "parent_id and child_id are required", "code": "bad_request"}), 400
    if parent_id == child_id:
        return jsonify({"error": "parent_id and child_id must differ", "code": "bad_request"}), 400

    repo = TreeRepository()
    if repo.get_person(parent_id) is None:
        return jsonify({"error": f"person not found: {parent_id}", "code": "not_found"}), 404
    if repo.get_person(child_id) is None:
        return jsonify({"error": f"person not found: {child_id}", "code": "not_found"}), 404

    rel = Relationship(parent_id=parent_id, child_id=child_id, rel_type=RelationshipType.BIOLOGICAL)
    repo.save_relationship(rel)
    return jsonify({"parent_id": parent_id, "child_id": child_id}), 201


@app.route("/api/unions", methods=["POST"])
@require_editor
def api_create_union():
    """Create a partnership/union between two people.

    Body: {"partner1_id": "...", "partner2_id": "..."}

    Returns 201 on success, 400 for missing fields, 404 if either person
    doesn't exist.
    """
    from models.relationship import Union
    body = request.get_json(silent=True) or {}
    p1 = (body.get("partner1_id") or "").strip()
    p2 = (body.get("partner2_id") or "").strip()
    if not p1 or not p2:
        return jsonify({"error": "partner1_id and partner2_id are required", "code": "bad_request"}), 400
    if p1 == p2:
        return jsonify({"error": "partner1_id and partner2_id must differ", "code": "bad_request"}), 400

    repo = TreeRepository()
    if repo.get_person(p1) is None:
        return jsonify({"error": f"person not found: {p1}", "code": "not_found"}), 404
    if repo.get_person(p2) is None:
        return jsonify({"error": f"person not found: {p2}", "code": "not_found"}), 404

    union = Union(partner1_id=p1, partner2_id=p2)
    repo.save_union(union)
    return jsonify({"partner1_id": p1, "partner2_id": p2}), 201


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


@app.route("/api/people/<person_id>/photos", methods=["POST"])
@require_editor
def api_add_photos(person_id):
    """Add photos to a person. Body: {"photo_paths": ["photos/foo.jpg"]}

    Idempotent: paths already on the person are silently skipped.

    Uses TreeRepository so it works on both SQLite (local) and PostgreSQL
    (production). Previously this endpoint issued raw SQL with SQLite-only
    placeholders, which silently failed against PostgreSQL.
    """
    body = request.get_json(force=True) or {}
    new_paths = body.get("photo_paths", [])
    if not new_paths:
        return jsonify({"error": "photo_paths required", "code": "missing_field"}), 400
    if not isinstance(new_paths, list):
        return jsonify({"error": "photo_paths must be a list", "code": "bad_type"}), 400

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    merged = list(person.photo_paths)
    for p in new_paths:
        if not isinstance(p, str) or not p:
            continue
        if p not in merged:
            merged.append(p)

    person.photo_paths = merged
    repo.save_person(person)
    return jsonify({"photo_paths": merged})


@app.route("/api/people/<person_id>/photos", methods=["DELETE"])
@require_editor
def api_remove_photo(person_id):
    """Remove a photo from a person. Body: {"photo_path": "photos/foo.jpg"}

    Uses TreeRepository so it works on both SQLite and PostgreSQL.
    """
    body = request.get_json(force=True) or {}
    photo_path = body.get("photo_path", "")
    if not photo_path:
        return jsonify({"error": "photo_path required", "code": "missing_field"}), 400

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    updated = [p for p in person.photo_paths if p != photo_path]
    # Also drop any caption associated with the removed photo.
    captions = dict(person.photo_captions)
    captions.pop(photo_path, None)

    person.photo_paths = updated
    person.photo_captions = captions
    repo.save_person(person)
    return jsonify({"photo_paths": updated})


ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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


@app.route("/api/photos/upload", methods=["POST"])
@require_editor
def api_upload_photo():
    """Upload a photo file. Returns ``{"path": "photos/..."}``.

    Hardened:
      - Rejects empty/missing filenames.
      - Rejects disallowed extensions.
      - Rejects zero-byte uploads.
      - Rejects uploads larger than ``MAX_PHOTO_BYTES``.
      - Rejects files whose magic bytes don't match the declared extension.
      - Writes atomically via ``.part`` rename so listings never see a
        half-written file.
    """
    if "photo" not in request.files:
        return jsonify({"error": "No file provided", "code": "missing_file"}), 400

    f = request.files["photo"]
    if not f.filename:
        return jsonify({"error": "Empty filename", "code": "empty_filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_PHOTO_EXTS:
        return jsonify({
            "error": f"Invalid file type: {ext or '(none)'}. Allowed: "
                     + ", ".join(sorted(ALLOWED_PHOTO_EXTS)),
            "code": "invalid_type",
        }), 400

    size = _measure_file_size(f)
    if size == 0:
        return jsonify({"error": "Empty file", "code": "empty"}), 400
    if size > MAX_PHOTO_BYTES:
        mb = MAX_PHOTO_BYTES // (1024 * 1024)
        return jsonify({
            "error": f"File too large (max {mb} MB)",
            "code": "too_large",
        }), 413

    safe_name = _sanitize_filename(f.filename)

    # Read file bytes for validation and storage
    file_data = f.read()

    # Validate magic bytes by writing to a temp file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_data)
        tmp_path = Path(tmp.name)
    try:
        if not _looks_like_image(tmp_path, ext):
            return jsonify({
                "error": "File contents do not match its extension",
                "code": "bad_content",
            }), 400
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    try:
        photo_storage.put(safe_name, file_data)
    except Exception as e:
        logger.error("photo save failed: %s", e)
        return jsonify({"error": "Could not save file", "code": "io_error"}), 500

    photo_path = f"photos/{safe_name}"
    repo = TreeRepository()
    photo_id = repo.get_or_create_photo(photo_path)

    # Extract EXIF metadata (date, GPS) and auto-populate
    exif = extract_exif_metadata(file_data)
    if exif:
        meta_update = {}
        photo = repo.get_photo(photo_id)
        if exif.get("date") and not photo.get("date"):
            meta_update["date"] = exif["date"]
        if exif.get("lat") is not None:
            meta_update["lat"] = exif["lat"]
        if exif.get("lng") is not None:
            meta_update["lng"] = exif["lng"]
        if meta_update:
            repo.update_photo_metadata(photo_id, **meta_update)

    return jsonify({"path": photo_path, "photo_id": photo_id, "exif": exif})


@app.route("/api/people/<person_id>/google-photos", methods=["POST"])
@require_editor
def api_import_google_photos(person_id):
    """Download photos from Google Photos URLs and attach them to a person.

    Body: {"items": [{"url": "https://...", "filename": "IMG_1234.jpg"}, ...]}

    Each URL is fetched server-side, saved to private/photos/, validated, and
    attached to the person. This lets everyone view the photo without needing
    the uploader's Google account.

    Returns: {"photo_paths": [...], "downloaded": N, "errors": [...]}
    """
    body = request.get_json(force=True) or {}
    items = body.get("items", [])
    if not items or not isinstance(items, list):
        return jsonify({"error": "items[] required", "code": "missing_field"}), 400
    if len(items) > 50:
        return jsonify({"error": "Too many items (max 50)", "code": "too_many"}), 400

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    merged = list(person.photo_paths)
    downloaded = 0
    errors = []

    for item in items:
        url = item.get("url", "")
        filename = item.get("filename", "photo.jpg")
        if not url:
            errors.append({"filename": filename, "error": "missing URL"})
            continue

        # Validate the URL is from Google domains
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            errors.append({"filename": filename, "error": "invalid URL"})
            continue
        allowed_hosts = (
            "lh3.googleusercontent.com",
            "lh4.googleusercontent.com",
            "lh5.googleusercontent.com",
            "lh6.googleusercontent.com",
            ".googleusercontent.com",
            ".ggpht.com",
            ".googleapis.com",
        )
        host_ok = any(
            parsed.hostname == h or parsed.hostname.endswith(h)
            for h in allowed_hosts
        )
        if not host_ok:
            errors.append({"filename": filename, "error": "URL not from Google"})
            continue

        safe_name = _sanitize_filename(filename)
        ext = Path(safe_name).suffix.lower()
        if ext not in ALLOWED_PHOTO_EXTS:
            # Default to .jpg for Google Photos URLs
            safe_name = Path(safe_name).stem + ".jpg"
            ext = ".jpg"

        try:
            req = __import__("urllib.request", fromlist=["urlopen", "Request"])
            r = req.Request(url)
            r.add_header("User-Agent", "FamilyTree/1.0")
            with req.urlopen(r, timeout=30) as resp:
                data = resp.read(MAX_PHOTO_BYTES + 1)
                if len(data) > MAX_PHOTO_BYTES:
                    errors.append({"filename": filename, "error": "file too large"})
                    continue
                if len(data) == 0:
                    errors.append({"filename": filename, "error": "empty file"})
                    continue

            # Validate image magic bytes via temp file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            try:
                if not _looks_like_image(tmp_path, ext):
                    errors.append({"filename": filename, "error": "not a valid image"})
                    continue
            finally:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

            photo_storage.put(safe_name, data)
            photo_path = f"photos/{safe_name}"
            if photo_path not in merged:
                merged.append(photo_path)
            downloaded += 1

        except (URLError, OSError, TimeoutError) as e:
            errors.append({"filename": filename, "error": str(e)})
            continue

    person.photo_paths = merged
    repo.save_person(person)
    result = {"photo_paths": merged, "downloaded": downloaded}
    if errors:
        result["errors"] = errors
    return jsonify(result)


@app.route("/api/people/<person_id>/photo-caption", methods=["PUT"])
@require_editor
def api_set_photo_caption(person_id):
    """Set caption for a photo on a person.

    Body: {"photo_path": "photos/foo.jpg", "caption": "Easter 1987"}

    An empty caption removes the caption entry. Uses TreeRepository so it
    works on both SQLite and PostgreSQL.
    """
    body = request.get_json(force=True) or {}
    photo_path = body.get("photo_path", "")
    caption = (body.get("caption") or "").strip()

    if not photo_path:
        return jsonify({"error": "photo_path required", "code": "missing_field"}), 400

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    captions = dict(person.photo_captions)
    if caption:
        captions[photo_path] = caption
    else:
        captions.pop(photo_path, None)

    person.photo_captions = captions
    repo.save_person(person)
    return jsonify({"photo_captions": captions})


# ── Photo Metadata & Tagging ───────────────────────────────────────


@app.route("/api/photos/<int:photo_id>/metadata", methods=["PUT"])
@require_editor
def api_update_photo_metadata(photo_id):
    """Update metadata for a photo (date, date_circa, place, photo_type).

    Body: {"date": "1987-04", "date_circa": true, "place": "NYC", "photo_type": "portrait"}
    """
    body = request.get_json(force=True) or {}
    repo = TreeRepository()
    photo = repo.get_photo(photo_id)
    if not photo:
        return jsonify({"error": "photo not found", "code": "not_found"}), 404

    kwargs = {}
    if "date" in body:
        kwargs["date"] = body["date"] or None
    if "date_circa" in body:
        kwargs["date_circa"] = bool(body["date_circa"])
    if "place" in body:
        kwargs["place"] = body["place"] or None
    if "photo_type" in body:
        pt = body["photo_type"]
        if pt not in ("portrait", "group", "document", "headstone", "photo"):
            return jsonify({"error": "invalid photo_type", "code": "bad_request"}), 400
        kwargs["photo_type"] = pt
    if "lat" in body:
        kwargs["lat"] = float(body["lat"]) if body["lat"] is not None else None
    if "lng" in body:
        kwargs["lng"] = float(body["lng"]) if body["lng"] is not None else None

    if kwargs:
        repo.update_photo_metadata(photo_id, **kwargs)

    updated = repo.get_photo(photo_id)
    return jsonify({
        "id": updated["id"],
        "file_path": updated["file_path"],
        "date": updated.get("date"),
        "date_circa": bool(updated.get("date_circa")),
        "place": updated.get("place"),
        "photo_type": updated.get("photo_type", "photo"),
        "lat": updated.get("lat"),
        "lng": updated.get("lng"),
    })


@app.route("/api/photos/bulk-metadata", methods=["PUT"])
@require_editor
def api_bulk_update_photo_metadata():
    """Update metadata for multiple photos at once.

    Body: {"photo_ids": [1, 2, 3], "date": "1985", "date_circa": true, ...}
    Same fields as single-photo metadata endpoint, applied to all listed photos.
    Max 200 photos per request.
    """
    body = request.get_json(force=True) or {}
    photo_ids = body.get("photo_ids", [])
    if not isinstance(photo_ids, list) or len(photo_ids) == 0:
        return jsonify({"error": "photo_ids must be a non-empty array", "code": "bad_request"}), 400
    if len(photo_ids) > 200:
        return jsonify({"error": "max 200 photos per request", "code": "bad_request"}), 400

    kwargs = {}
    if "date" in body:
        kwargs["date"] = body["date"] or None
    if "date_circa" in body:
        kwargs["date_circa"] = bool(body["date_circa"])
    if "place" in body:
        kwargs["place"] = body["place"] or None
    if "photo_type" in body:
        pt = body["photo_type"]
        if pt not in ("portrait", "group", "document", "headstone", "photo"):
            return jsonify({"error": "invalid photo_type", "code": "bad_request"}), 400
        kwargs["photo_type"] = pt
    if "lat" in body:
        kwargs["lat"] = float(body["lat"]) if body["lat"] is not None else None
    if "lng" in body:
        kwargs["lng"] = float(body["lng"]) if body["lng"] is not None else None

    if not kwargs:
        return jsonify({"error": "no metadata fields provided", "code": "bad_request"}), 400

    repo = TreeRepository()
    updated = []
    not_found = []
    for pid in photo_ids:
        photo = repo.get_photo(pid)
        if not photo:
            not_found.append(pid)
            continue
        repo.update_photo_metadata(pid, **kwargs)
        updated.append(pid)

    return jsonify({"updated": updated, "not_found": not_found})


@app.route("/api/photos/reextract-exif", methods=["POST"])
@require_editor
def api_reextract_exif():
    """Bulk re-extract EXIF metadata for photos missing date and GPS.

    Fetches image bytes for each photo where lat IS NULL AND date IS NULL,
    runs EXIF extraction, and updates metadata.

    Returns {"updated": N}
    """
    repo = TreeRepository()
    conn = get_connection()
    try:
        from database.repository import _fetchall
        rows = _fetchall(conn, "SELECT id, file_path FROM photos WHERE lat IS NULL AND date IS NULL")
    finally:
        conn.close()

    updated = 0
    for row in rows:
        file_path = row["file_path"]
        # Strip "photos/" prefix for storage lookup
        filename = file_path.replace("photos/", "", 1) if file_path.startswith("photos/") else file_path
        data = photo_storage.get(filename)
        if not data:
            continue
        exif = extract_exif_metadata(data)
        if not exif:
            continue
        meta = {}
        if exif.get("date"):
            meta["date"] = exif["date"]
        if exif.get("lat") is not None:
            meta["lat"] = exif["lat"]
        if exif.get("lng") is not None:
            meta["lng"] = exif["lng"]
        if meta:
            repo.update_photo_metadata(row["id"], **meta)
            updated += 1

    return jsonify({"updated": updated})


@app.route("/api/people/<person_id>/profile-photo", methods=["PUT"])
@require_editor
def api_set_profile_photo(person_id):
    """Set the profile photo for a person. Body: {"photo_id": N}"""
    body = request.get_json(force=True) or {}
    photo_id = body.get("photo_id")
    if not photo_id:
        return jsonify({"error": "photo_id required", "code": "missing_field"}), 400

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    repo.set_profile_photo(person_id, int(photo_id))

    # Also sync the old photo_paths array so the profile photo is first
    photo = repo.get_photo(int(photo_id))
    if photo and photo["file_path"] in person.photo_paths:
        paths = list(person.photo_paths)
        paths.remove(photo["file_path"])
        paths.insert(0, photo["file_path"])
        person.photo_paths = paths
        repo.save_person(person)

    return jsonify({"ok": True, "photo_id": photo_id})


@app.route("/api/photos/<int:photo_id>/tag", methods=["POST"])
@require_editor
def api_tag_person_in_photo(photo_id):
    """Tag a person in a photo. Body: {"person_id": "..."}"""
    body = request.get_json(force=True) or {}
    person_id = (body.get("person_id") or "").strip()
    if not person_id:
        return jsonify({"error": "person_id required", "code": "missing_field"}), 400

    repo = TreeRepository()
    photo = repo.get_photo(photo_id)
    if not photo:
        return jsonify({"error": "photo not found", "code": "not_found"}), 404
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    # Get current max display_order for this person
    existing = repo.photos_for_person(person_id)
    max_order = max((p.get("display_order", 0) for p in existing), default=-1)

    repo.assign_photo_to_person(person_id, photo_id, display_order=max_order + 1)

    # Also add to old photo_paths for backward compat
    if photo["file_path"] not in person.photo_paths:
        person.photo_paths = list(person.photo_paths) + [photo["file_path"]]
        repo.save_person(person)

    return jsonify({"ok": True}), 201


@app.route("/api/photos/<int:photo_id>/tag/<person_id>", methods=["DELETE"])
@require_editor
def api_untag_person_from_photo(photo_id, person_id):
    """Remove a person's tag from a photo."""
    repo = TreeRepository()
    repo.unassign_photo_from_person(person_id, photo_id)

    # Also remove from old photo_paths for backward compat
    photo = repo.get_photo(photo_id)
    person = repo.get_person(person_id)
    if photo and person and photo["file_path"] in person.photo_paths:
        person.photo_paths = [p for p in person.photo_paths if p != photo["file_path"]]
        captions = dict(person.photo_captions)
        captions.pop(photo["file_path"], None)
        person.photo_captions = captions
        repo.save_person(person)

    return ("", 204)


# ── Face Regions ───────────────────────────────────────────────────────


@app.route("/api/photos/<int:photo_id>/face-region", methods=["PUT"])
@require_editor
def api_save_face_region(photo_id):
    """Save a face region for a person on a photo.

    Body: {"person_id": "...", "x": 0.2, "y": 0.1, "w": 0.3, "h": 0.4}
    Coordinates are normalized 0-1.
    """
    body = request.get_json(force=True) or {}
    person_id = (body.get("person_id") or "").strip()
    if not person_id:
        return jsonify({"error": "person_id required", "code": "missing_field"}), 400

    try:
        x = float(body.get("x", -1))
        y = float(body.get("y", -1))
        w = float(body.get("w", -1))
        h = float(body.get("h", -1))
    except (TypeError, ValueError):
        return jsonify({"error": "x, y, w, h must be numbers", "code": "bad_request"}), 400

    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
        return jsonify({"error": "coordinates must be in 0-1 range", "code": "bad_request"}), 400
    if x + w > 1.001 or y + h > 1.001:
        return jsonify({"error": "region extends beyond image bounds", "code": "bad_request"}), 400

    repo = TreeRepository()
    photo = repo.get_photo(photo_id)
    if not photo:
        return jsonify({"error": "photo not found", "code": "not_found"}), 404
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    region_id = repo.save_face_region(photo_id, person_id, x, y, w, h)

    # Auto-tag: if this person isn't already tagged in the photo, add them.
    # This makes the photo show up on the tagged person's panel.
    existing_people = repo.people_for_photo(photo_id)
    already_tagged = {p["person_id"] for p in existing_people}
    if person_id not in already_tagged:
        max_order = max((p.get("display_order", 0) for p in existing_people), default=-1)
        repo.assign_photo_to_person(person_id, photo_id, display_order=max_order + 1)
        # Also add to old photo_paths for backward compat
        if photo["file_path"] not in person.photo_paths:
            person.photo_paths = list(person.photo_paths) + [photo["file_path"]]
            repo.save_person(person)

    return jsonify({"id": region_id, "photo_id": photo_id, "person_id": person_id,
                    "x": x, "y": y, "w": w, "h": h, "auto_tagged": person_id not in already_tagged})


@app.route("/api/photos/<int:photo_id>/face-regions")
def api_get_face_regions(photo_id):
    """Return all face regions for a photo."""
    repo = TreeRepository()
    regions = repo.get_face_regions(photo_id)
    return jsonify([
        {
            "id": r["id"],
            "photo_id": r["photo_id"],
            "person_id": r["person_id"],
            "x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"],
            "given_name": r.get("given_name", ""),
            "surname": r.get("surname", ""),
        }
        for r in regions
    ])


@app.route("/api/photos/<int:photo_id>/face-region/<int:region_id>", methods=["DELETE"])
@require_editor
def api_delete_face_region(photo_id, region_id):
    """Delete a face region."""
    repo = TreeRepository()
    repo.delete_face_region(region_id)
    return ("", 204)


# ── Profile Crop ──────────────────────────────────────────────────────


@app.route("/api/people/<person_id>/profile-crop", methods=["PUT"])
@require_editor
def api_set_profile_crop(person_id):
    """Set the crop region for a person's profile photo.

    Body: {"photo_id": N, "crop_x": 0.1, "crop_y": 0.1, "crop_w": 0.5, "crop_h": 0.5}
    """
    body = request.get_json(force=True) or {}
    photo_id = body.get("photo_id")
    if not photo_id:
        return jsonify({"error": "photo_id required", "code": "missing_field"}), 400

    try:
        crop_x = float(body.get("crop_x", -1))
        crop_y = float(body.get("crop_y", -1))
        crop_w = float(body.get("crop_w", -1))
        crop_h = float(body.get("crop_h", -1))
    except (TypeError, ValueError):
        return jsonify({"error": "crop values must be numbers", "code": "bad_request"}), 400

    if not (0 <= crop_x <= 1 and 0 <= crop_y <= 1 and 0 < crop_w <= 1 and 0 < crop_h <= 1):
        return jsonify({"error": "crop coordinates must be in 0-1 range", "code": "bad_request"}), 400
    if crop_x + crop_w > 1.001 or crop_y + crop_h > 1.001:
        return jsonify({"error": "crop region extends beyond image bounds", "code": "bad_request"}), 400

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    repo.set_profile_crop(person_id, int(photo_id), crop_x, crop_y, crop_w, crop_h)
    return jsonify({"ok": True, "person_id": person_id, "photo_id": photo_id,
                    "crop_x": crop_x, "crop_y": crop_y, "crop_w": crop_w, "crop_h": crop_h})


@app.route("/api/people/<person_id>/profile-crop", methods=["DELETE"])
@require_editor
def api_clear_profile_crop(person_id):
    """Clear the crop region for a person's profile photo."""
    body = request.get_json(force=True) or {}
    photo_id = body.get("photo_id")
    if not photo_id:
        return jsonify({"error": "photo_id required", "code": "missing_field"}), 400

    repo = TreeRepository()
    repo.clear_profile_crop(person_id, int(photo_id))
    return jsonify({"ok": True})


# ── Document Upload & AI Parsing ───────────────────────────────────────

ALLOWED_DOC_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}


def _update_document(doc_id: str, *, status: str | None = None, parsed_data: dict | None = None) -> None:
    """Portable helper that updates a documents row on either backend."""
    sets = []
    params: list = []
    if status is not None:
        sets.append(f"status = {_ph()}")
        params.append(status)
    if parsed_data is not None:
        sets.append(f"parsed_data = {_ph()}")
        params.append(json.dumps(parsed_data))
    if not sets:
        return
    params.append(doc_id)
    sql = f"UPDATE documents SET {', '.join(sets)} WHERE id = {_ph()}"
    conn = get_connection()
    try:
        _execute(conn, sql, tuple(params))
        conn.commit()
    finally:
        conn.close()


def _get_document(doc_id: str) -> dict | None:
    conn = get_connection()
    try:
        return _fetchone(
            conn,
            f"SELECT * FROM documents WHERE id = {_ph()}",
            (doc_id,),
        )
    finally:
        conn.close()


@app.route("/api/import/gedcom", methods=["POST"])
@require_editor
def api_import_gedcom():
    """Import a GEDCOM (.ged) file into the database.

    Returns summary stats: people, unions, relationships, events imported.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in (".ged", ".gedcom"):
        return jsonify({"error": f"Expected a .ged file, got {ext or '(none)'}"}), 400

    # Save to a temp file for parsing
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".ged", delete=False)
    try:
        f.save(tmp.name)
        tree = parse_gedcom(tmp.name)
    except Exception as e:
        logger.error("GEDCOM parse failed: %s", e)
        return jsonify({"error": f"Failed to parse GEDCOM file: {e}"}), 400
    finally:
        try:
            Path(tmp.name).unlink()
        except OSError:
            pass

    # Persist everything via the repository
    repo = TreeRepository()
    stats = {"people": 0, "unions": 0, "relationships": 0, "events": 0, "skipped": []}

    for person in tree.people.values():
        try:
            repo.save_person(person)
            stats["people"] += 1
        except Exception as e:
            stats["skipped"].append(f"Person {person.id}: {e}")

    for union in tree.unions:
        try:
            repo.save_union(union)
            stats["unions"] += 1
        except Exception as e:
            stats["skipped"].append(f"Union: {e}")

    for rel in tree.relationships:
        try:
            repo.save_relationship(rel)
            stats["relationships"] += 1
        except Exception as e:
            stats["skipped"].append(f"Relationship: {e}")

    for event in tree.events:
        try:
            repo.save_event(event)
            stats["events"] += 1
        except Exception as e:
            stats["skipped"].append(f"Event: {e}")

    return jsonify(stats)


@app.route("/api/documents/upload", methods=["POST"])
@require_editor
def api_upload_document():
    """Upload a document for AI parsing.

    Returns ``{"document_id": "...", "filename": "...", "status": "uploaded"}``.

    Hardened in the same ways as ``/api/photos/upload`` (size cap, magic-byte
    check, atomic write) plus transactional cleanup: if the DB insert fails,
    the saved file is removed so we don't leave orphans on disk.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided", "code": "missing_file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename", "code": "empty_filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXTS:
        return jsonify({
            "error": f"Unsupported file type: {ext or '(none)'}. Use images or PDF.",
            "code": "invalid_type",
        }), 400

    size = _measure_file_size(f)
    if size == 0:
        return jsonify({"error": "Empty file", "code": "empty"}), 400
    if size > MAX_DOC_BYTES:
        mb = MAX_DOC_BYTES // (1024 * 1024)
        return jsonify({
            "error": f"File too large (max {mb} MB)",
            "code": "too_large",
        }), 413

    doc_id = str(uuid.uuid4())[:12]
    safe_name = _sanitize_filename(f.filename)
    doc_dir = PRIVATE_DIR / "documents"
    dest = doc_dir / safe_name

    try:
        _atomic_save(f, dest)
    except OSError as e:
        logger.error("document save failed: %s", e)
        return jsonify({"error": "Could not save file", "code": "io_error"}), 500

    # Magic-byte check post-save
    is_pdf = ext == ".pdf"
    ok = _looks_like_pdf(dest) if is_pdf else _looks_like_image(dest, ext)
    if not ok:
        try:
            dest.unlink()
        except OSError:
            pass
        return jsonify({
            "error": "File contents do not match its extension",
            "code": "bad_content",
        }), 400

    file_type = "pdf" if is_pdf else "image"
    uploaded_by = session.get("person_id")

    conn = get_connection()
    try:
        try:
            _execute(
                conn,
                f"INSERT INTO documents (id, filename, file_path, file_type, uploaded_by) "
                f"VALUES ({_ph(5)})",
                (doc_id, f.filename, f"documents/{safe_name}", file_type, uploaded_by),
            )
            conn.commit()
        except Exception as e:
            # Transactional cleanup: if the DB insert fails, don't leave
            # the file sitting on disk with no tracking row.
            try:
                if dest.exists():
                    dest.unlink()
            except OSError:
                pass
            logger.error("document DB insert failed: %s", e)
            return jsonify({
                "error": "Could not record document",
                "code": "db_error",
            }), 500
    finally:
        conn.close()

    return jsonify({
        "document_id": doc_id,
        "filename": f.filename,
        "file_type": file_type,
        "status": "uploaded",
    })


@app.route("/api/documents/<doc_id>/parse", methods=["POST"])
@require_editor
def api_parse_document(doc_id):
    """Trigger AI parsing of a document. Returns proposed changes for review."""
    row = _get_document(doc_id)
    if not row:
        return jsonify({"error": "Document not found", "code": "not_found"}), 404

    file_path = str(PRIVATE_DIR / row["file_path"])
    if not Path(file_path).exists():
        return jsonify({"error": "Document file not found on disk", "code": "missing_file"}), 404

    _update_document(doc_id, status="parsing")

    # Get existing people for matching
    repo = TreeRepository()
    tree = repo.load_tree()
    existing_people = [
        {
            "id": p.id,
            "given_name": p.given_name,
            "surname": p.surname,
            "birth_date": p.birth_date,
            "death_date": p.death_date,
            "maiden_name": p.maiden_name,
            "gender": p.gender.value,
        }
        for p in tree.people.values()
    ]

    # Run AI parsing
    try:
        from intelligence.document_parser import parse_document
        result = parse_document(
            file_path=file_path,
            existing_people=existing_people,
            document_filename=row["filename"],
        )
    except Exception as e:
        logger.error("Document parsing failed: %s", e)
        _update_document(doc_id, status="error", parsed_data={"error": str(e)})
        return jsonify({"error": f"Parsing failed: {e}", "code": "parse_failed"}), 500

    # Check for error in result
    if "error" in result:
        _update_document(doc_id, status="error", parsed_data=result)
        return jsonify(result), 500

    _update_document(doc_id, status="parsed", parsed_data=result)

    return jsonify({
        "document_id": doc_id,
        "status": "parsed",
        "proposed_changes": result,
    })


@app.route("/api/documents/<doc_id>/apply", methods=["POST"])
@require_editor
def api_apply_document(doc_id):
    """Apply reviewed/edited changes from a parsed document to the database.

    Body: The proposed_changes JSON (possibly edited by user in the review modal).
    """
    changes = request.get_json(force=True) or {}

    row = _get_document(doc_id)
    if not row:
        return jsonify({"error": "Document not found", "code": "not_found"}), 404

    repo = TreeRepository()
    applied = {"people": 0, "relationships": 0, "events": 0, "unions": 0}

    # Create a Source for this document
    from models.source import Source, SourceType
    source = Source(
        id=f"doc-{doc_id}",
        name=row["filename"],
        source_type=SourceType.DOCUMENT,
        description=changes.get("summary", "Uploaded document"),
    )
    repo.save_source(source)

    # Apply people
    from models.person import Person, Gender
    for p_data in changes.get("people", []):
        person_id = p_data.get("id", "")
        if not person_id or not p_data.get("given_name"):
            continue

        # Check if person exists
        existing = repo.get_person(person_id)
        if existing:
            # Update fields that are currently empty
            changed = False
            for field in ("birth_date", "birth_place", "death_date", "death_place", "maiden_name"):
                new_val = p_data.get(field)
                if new_val and not getattr(existing, field):
                    setattr(existing, field, new_val)
                    changed = True
            if p_data.get("notes") and not existing.notes:
                existing.notes = p_data["notes"]
                changed = True
            if changed:
                repo.save_person(existing)
                applied["people"] += 1
        elif p_data.get("is_new"):
            # Create new person
            gender_val = p_data.get("gender", "unknown")
            try:
                gender = Gender(gender_val)
            except ValueError:
                gender = Gender.UNKNOWN

            person = Person(
                id=person_id,
                given_name=p_data["given_name"],
                surname=p_data.get("surname", ""),
                gender=gender,
                birth_date=p_data.get("birth_date"),
                birth_place=p_data.get("birth_place"),
                death_date=p_data.get("death_date"),
                death_place=p_data.get("death_place"),
                maiden_name=p_data.get("maiden_name"),
                notes=p_data.get("notes", ""),
            )
            repo.save_person(person)
            applied["people"] += 1

    # Apply relationships
    from models.relationship import Relationship, RelationshipType
    for r_data in changes.get("relationships", []):
        parent_id = r_data.get("parent_id", "")
        child_id = r_data.get("child_id", "")
        if not parent_id or not child_id:
            continue
        try:
            rel_type = RelationshipType(r_data.get("rel_type", "biological"))
        except ValueError:
            rel_type = RelationshipType.BIOLOGICAL
        rel = Relationship(parent_id=parent_id, child_id=child_id, rel_type=rel_type)
        try:
            repo.save_relationship(rel)
            applied["relationships"] += 1
        except Exception as e:
            logger.warning("Could not save relationship %s→%s: %s", parent_id, child_id, e)

    # Apply events
    from models.event import LifeEvent, EventType
    for e_data in changes.get("events", []):
        person_id = e_data.get("person_id", "")
        if not person_id:
            continue
        try:
            event_type = EventType(e_data.get("event_type", "custom"))
        except ValueError:
            event_type = EventType.CUSTOM
        event = LifeEvent(
            person_id=person_id,
            event_type=event_type,
            date=e_data.get("date"),
            end_date=e_data.get("end_date"),
            place=e_data.get("place"),
            description=e_data.get("description", ""),
            source=f"doc-{doc_id}",
        )
        try:
            repo.save_event(event)
            applied["events"] += 1
        except Exception as e:
            logger.warning("Could not save event for %s: %s", person_id, e)

    # Apply unions
    from models.relationship import Union
    for u_data in changes.get("unions", []):
        p1 = u_data.get("partner1_id", "")
        p2 = u_data.get("partner2_id", "")
        if not p1 or not p2:
            continue
        union = Union(
            partner1_id=p1,
            partner2_id=p2,
            union_date=u_data.get("union_date"),
            union_place=u_data.get("union_place"),
        )
        try:
            repo.save_union(union)
            applied["unions"] += 1
        except Exception as e:
            logger.warning("Could not save union %s + %s: %s", p1, p2, e)

    # Update document status
    _update_document(doc_id, status="applied")

    return jsonify({"status": "applied", "applied": applied})


@app.route("/documents/<path:filename>")
def serve_document(filename):
    """Serve uploaded documents from private/documents/."""
    doc_dir = PRIVATE_DIR / "documents"
    if (doc_dir / filename).exists():
        return send_from_directory(str(doc_dir), filename)
    abort(404)


# ── Authentication ─────────────────────────────────────────────────────

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


GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def _verify_id_token(credential: str) -> dict | None:
    """Verify a Google ID token via the tokeninfo endpoint.

    Returns the token payload dict on success, or None on failure.
    Matches the pattern used in the Sutro dashboard.
    """
    try:
        url = f"{GOOGLE_TOKENINFO_URL}?id_token={credential}"
        with urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read())
    except (URLError, ValueError, OSError) as e:
        logger.warning("tokeninfo request failed: %s", e)
        return None


@app.route("/api/auth/google", methods=["POST"])
def api_auth_google():
    """Authenticate with a Google ID token.

    Body: {"credential": "<google id_token>"}
    Returns: {"person_id": "...", "name": "...", "email": "..."}
    """
    body = request.get_json(force=True)
    credential = body.get("credential", "")
    if not credential:
        return jsonify({"error": "credential required"}), 400

    # Verify token with Google
    payload = _verify_id_token(credential)
    if not payload:
        return jsonify({"error": "Invalid Google token"}), 401

    email = (payload.get("email") or "").lower()
    if not email or payload.get("email_verified") != "true":
        return jsonify({"error": "Email not verified"}), 401

    # Validate audience matches our client ID
    client_id = _get_google_client_id()
    if client_id:
        aud = payload.get("aud", "")
        if aud != client_id:
            logger.warning("Token aud %s does not match expected client_id", aud)
            return jsonify({"error": "Token audience mismatch"}), 401

    # When no EDITORS list is configured everyone is treated as an editor
    # (preserves the original open-access behaviour).
    is_editor = (not EDITORS) or (email in EDITORS)

    # Editors can sign in even without a person record in the tree.
    # Non-editors must have a matching person record (existing behaviour).
    repo = TreeRepository()
    person = repo.get_person_by_email(email)
    if not person and not is_editor:
        return jsonify({
            "error": "No matching person record for this email",
            "email": email,
        }), 403

    person_id = person.id if person else f"editor:{email}"
    full_name = person.full_name if person else payload.get("name", email)

    # Set session
    session["person_id"] = person_id
    session["email"] = email
    session["name"] = full_name
    session["picture"] = payload.get("picture", "")
    session["is_editor"] = is_editor

    return jsonify({
        "person_id": person_id,
        "name": full_name,
        "email": email,
        "picture": payload.get("picture", ""),
        "is_editor": is_editor,
    })


@app.route("/api/auth/me")
def api_auth_me():
    """Return the current logged-in user, or 401."""
    if "person_id" not in session:
        return jsonify({"error": "not authenticated"}), 401
    return jsonify({
        "person_id": session["person_id"],
        "name": session.get("name", ""),
        "email": session.get("email", ""),
        "picture": session.get("picture", ""),
        "is_editor": session.get("is_editor", False),
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Clear the session."""
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/people/<person_id>/email", methods=["PUT"])
def api_set_email(person_id):
    """Set the email for a person. Body: {"email": "user@example.com"}

    Only the admin (admin) can set emails for other people.
    Any logged-in user can clear their own email.
    """
    # Simple admin check — only Dustin can assign emails
    admin_id = session.get("person_id")
    if admin_id != "dustin":
        return jsonify({"error": "admin only"}), 403

    body = request.get_json(force=True) or {}
    email = body.get("email", "").strip().lower() or None

    conn = get_connection()
    try:
        _execute(
            conn,
            f"UPDATE people SET email = {_ph()} WHERE id = {_ph()}",
            (email, person_id),
        )
        conn.commit()
        return jsonify({"email": email, "person_id": person_id})
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
