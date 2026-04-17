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
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from flask import Flask, jsonify, request, send_from_directory, abort, session

from database.connection import get_connection, init_db
from database.repository import TreeRepository

logger = logging.getLogger(__name__)
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
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit


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


@app.route("/api/geocode", methods=["POST"])
def api_geocode():
    """Geocode a list of place strings via Nominatim (with DB cache).

    Body: JSON array of place strings.
    Returns: {place: [lat, lng]} for every place that resolved.
    """
    from geocoder import geocode_places
    places = request.get_json(silent=True) or []
    if not isinstance(places, list):
        return jsonify({"error": "expected a JSON array"}), 400
    coords = geocode_places(places)
    return jsonify({p: list(c) for p, c in coords.items() if c is not None})


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
    """Return a list of all photo files from private/photos/ and web/photos/."""
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    seen = set()
    photos = []
    for photo_dir in [PRIVATE_DIR / "photos", Path(WEB_DIR) / "photos"]:
        if not photo_dir.is_dir():
            continue
        for f in photo_dir.iterdir():
            if f.suffix.lower() in exts and f.name not in seen:
                seen.add(f.name)
                photos.append(f"photos/{f.name}")
    return jsonify(sorted(photos))


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


ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _sanitize_filename(name: str) -> str:
    """Turn a filename into a safe slug with timestamp prefix."""
    stem = Path(name).stem
    ext = Path(name).suffix.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")[:80]
    ts = int(time.time())
    return f"{ts}-{slug}{ext}"


@app.route("/api/photos/upload", methods=["POST"])
def api_upload_photo():
    """Upload a photo file. Returns {"path": "photos/..."}."""
    if "photo" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["photo"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_PHOTO_EXTS:
        return jsonify({"error": f"Invalid file type: {ext}"}), 400

    safe_name = _sanitize_filename(f.filename)
    photo_dir = PRIVATE_DIR / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)

    dest = photo_dir / safe_name
    f.save(str(dest))

    return jsonify({"path": f"photos/{safe_name}"})


@app.route("/api/people/<person_id>/photo-caption", methods=["PUT"])
def api_set_photo_caption(person_id):
    """Set caption for a photo on a person.

    Body: {"photo_path": "photos/foo.jpg", "caption": "Easter 1987"}
    """
    body = request.get_json(force=True)
    photo_path = body.get("photo_path", "")
    caption = body.get("caption", "").strip()

    if not photo_path:
        return jsonify({"error": "photo_path required"}), 400

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT photo_captions FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "person not found"}), 404

        captions = json.loads(row["photo_captions"] or "{}")
        if caption:
            captions[photo_path] = caption
        else:
            captions.pop(photo_path, None)

        conn.execute(
            "UPDATE people SET photo_captions = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(captions), person_id),
        )
        conn.commit()
        return jsonify({"photo_captions": captions})
    finally:
        conn.close()


# ── Document Upload & AI Parsing ───────────────────────────────────────

import uuid

ALLOWED_DOC_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}


@app.route("/api/documents/upload", methods=["POST"])
def api_upload_document():
    """Upload a document for AI parsing.

    Returns: {"document_id": "...", "filename": "...", "status": "uploaded"}
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXTS:
        return jsonify({"error": f"Unsupported file type: {ext}. Use images or PDF."}), 400

    doc_id = str(uuid.uuid4())[:12]
    safe_name = _sanitize_filename(f.filename)
    doc_dir = PRIVATE_DIR / "documents"
    doc_dir.mkdir(parents=True, exist_ok=True)

    dest = doc_dir / safe_name
    f.save(str(dest))

    # Record in DB
    file_type = "pdf" if ext == ".pdf" else "image"
    uploaded_by = session.get("person_id")

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO documents (id, filename, file_path, file_type, uploaded_by) VALUES (?, ?, ?, ?, ?)",
            (doc_id, f.filename, f"documents/{safe_name}", file_type, uploaded_by),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "document_id": doc_id,
        "filename": f.filename,
        "file_type": file_type,
        "status": "uploaded",
    })


@app.route("/api/documents/<doc_id>/parse", methods=["POST"])
def api_parse_document(doc_id):
    """Trigger AI parsing of a document. Returns proposed changes for review."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return jsonify({"error": "Document not found"}), 404

        file_path = str(PRIVATE_DIR / row["file_path"])
        if not Path(file_path).exists():
            return jsonify({"error": "Document file not found on disk"}), 404

        # Update status to parsing
        conn.execute(
            "UPDATE documents SET status = 'parsing' WHERE id = ?", (doc_id,)
        )
        conn.commit()
    finally:
        conn.close()

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
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE documents SET status = 'error', parsed_data = ? WHERE id = ?",
                (json.dumps({"error": str(e)}), doc_id),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"error": f"Parsing failed: {e}"}), 500

    # Check for error in result
    if "error" in result:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE documents SET status = 'error', parsed_data = ? WHERE id = ?",
                (json.dumps(result), doc_id),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify(result), 500

    # Save parsed data and update status
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE documents SET status = 'parsed', parsed_data = ? WHERE id = ?",
            (json.dumps(result), doc_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "document_id": doc_id,
        "status": "parsed",
        "proposed_changes": result,
    })


@app.route("/api/documents/<doc_id>/apply", methods=["POST"])
def api_apply_document(doc_id):
    """Apply reviewed/edited changes from a parsed document to the database.

    Body: The proposed_changes JSON (possibly edited by user in the review modal).
    """
    changes = request.get_json(force=True)

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return jsonify({"error": "Document not found"}), 404
    finally:
        conn.close()

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
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE documents SET status = 'applied' WHERE id = ?", (doc_id,)
        )
        conn.commit()
    finally:
        conn.close()

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

    # Look up the person by email
    repo = TreeRepository()
    person = repo.get_person_by_email(email)
    if not person:
        return jsonify({
            "error": "No matching person record for this email",
            "email": email,
        }), 403

    # Set session
    session["person_id"] = person.id
    session["email"] = email
    session["name"] = person.full_name
    session["picture"] = payload.get("picture", "")

    return jsonify({
        "person_id": person.id,
        "name": person.full_name,
        "email": email,
        "picture": payload.get("picture", ""),
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

    body = request.get_json(force=True)
    email = body.get("email", "").strip().lower() or None

    conn = get_connection()
    try:
        if os.environ.get("DATABASE_URL"):
            cur = conn.cursor()
            cur.execute(
                "UPDATE people SET email = %s WHERE id = %s",
                (email, person_id),
            )
        else:
            conn.execute(
                "UPDATE people SET email = ? WHERE id = ?",
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
