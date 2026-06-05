"""Photo upload, tagging, metadata, face regions, and profile crop endpoints."""

import logging
import tempfile
from pathlib import Path
from urllib.error import URLError

from flask import Blueprint, jsonify, request

import storage
import web_server
from database.connection import get_connection
from database.repository import TreeRepository
from exif_utils import extract_exif_metadata

logger = logging.getLogger(__name__)

photos_bp = Blueprint("photos", __name__)


def _person_photo_paths(repo, person_id):
    """A person's photo paths, ordered by display_order, from person_photos."""
    return [r["file_path"] for r in repo.photos_for_person(person_id)]


def _person_photo_captions(repo, person_id):
    """A person's {file_path: caption} map (non-empty captions) from person_photos."""
    return {
        r["file_path"]: r["caption"] for r in repo.photos_for_person(person_id) if r.get("caption")
    }


@photos_bp.route("/api/people/<person_id>/photos", methods=["POST"])
@web_server.require_editor
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

    # Write straight to person_photos (the authoritative store). Idempotent:
    # paths already linked to this person are skipped.
    existing = {r["file_path"]: r for r in repo.photos_for_person(person_id)}
    max_order = max((r.get("display_order", 0) for r in existing.values()), default=-1)
    for p in new_paths:
        if not isinstance(p, str) or not p or p in existing:
            continue
        max_order += 1
        repo.assign_photo_to_person(person_id, repo.get_or_create_photo(p), display_order=max_order)

    return jsonify({"photo_paths": _person_photo_paths(repo, person_id)})


@photos_bp.route("/api/people/<person_id>/photos", methods=["DELETE"])
@web_server.require_editor
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

    # Remove the link from person_photos (the authoritative store); the caption
    # lives on that row, so it's dropped with it.
    match = next(
        (ph for ph in repo.photos_for_person(person_id) if ph["file_path"] == photo_path), None
    )
    if match:
        repo.unassign_photo_from_person(person_id, match["id"])
    return jsonify({"photo_paths": _person_photo_paths(repo, person_id)})


@photos_bp.route("/api/photos/upload", methods=["POST"])
@web_server.require_editor
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
    if ext not in web_server.ALLOWED_PHOTO_EXTS:
        return jsonify(
            {
                "error": f"Invalid file type: {ext or '(none)'}. Allowed: "
                + ", ".join(sorted(web_server.ALLOWED_PHOTO_EXTS)),
                "code": "invalid_type",
            }
        ), 400

    size = web_server._measure_file_size(f)
    if size == 0:
        return jsonify({"error": "Empty file", "code": "empty"}), 400
    if size > web_server.MAX_PHOTO_BYTES:
        mb = web_server.MAX_PHOTO_BYTES // (1024 * 1024)
        return jsonify(
            {
                "error": f"File too large (max {mb} MB)",
                "code": "too_large",
            }
        ), 413

    safe_name = web_server._sanitize_filename(f.filename)

    # Read file bytes for validation and storage
    file_data = f.read()

    # Validate magic bytes by writing to a temp file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_data)
        tmp_path = Path(tmp.name)
    try:
        if not web_server._looks_like_image(tmp_path, ext):
            return jsonify(
                {
                    "error": "File contents do not match its extension",
                    "code": "bad_content",
                }
            ), 400
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    try:
        storage.photo_storage.put(safe_name, file_data)
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


@photos_bp.route("/api/people/<person_id>/google-photos", methods=["POST"])
@web_server.require_editor
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

    existing = {r["file_path"] for r in repo.photos_for_person(person_id)}
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
        host_ok = any(parsed.hostname == h or parsed.hostname.endswith(h) for h in allowed_hosts)
        if not host_ok:
            errors.append({"filename": filename, "error": "URL not from Google"})
            continue

        safe_name = web_server._sanitize_filename(filename)
        ext = Path(safe_name).suffix.lower()
        if ext not in web_server.ALLOWED_PHOTO_EXTS:
            # Default to .jpg for Google Photos URLs
            safe_name = Path(safe_name).stem + ".jpg"
            ext = ".jpg"

        try:
            req = __import__("urllib.request", fromlist=["urlopen", "Request"])
            r = req.Request(url)
            r.add_header("User-Agent", "FamilyTree/1.0")
            with req.urlopen(r, timeout=30) as resp:
                data = resp.read(web_server.MAX_PHOTO_BYTES + 1)
                if len(data) > web_server.MAX_PHOTO_BYTES:
                    errors.append({"filename": filename, "error": "file too large"})
                    continue
                if len(data) == 0:
                    errors.append({"filename": filename, "error": "empty file"})
                    continue

            # Validate image magic bytes via temp file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            try:
                if not web_server._looks_like_image(tmp_path, ext):
                    errors.append({"filename": filename, "error": "not a valid image"})
                    continue
            finally:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

            storage.photo_storage.put(safe_name, data)
            photo_path = f"photos/{safe_name}"
            if photo_path not in existing:
                repo.assign_photo_to_person(person_id, repo.get_or_create_photo(photo_path))
                existing.add(photo_path)
            downloaded += 1

        except (URLError, OSError, TimeoutError) as e:
            errors.append({"filename": filename, "error": str(e)})
            continue

    result = {"photo_paths": _person_photo_paths(repo, person_id), "downloaded": downloaded}
    if errors:
        result["errors"] = errors
    return jsonify(result)


@photos_bp.route("/api/people/<person_id>/photo-caption", methods=["PUT"])
@web_server.require_editor
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

    # Caption lives on the person_photos link (empty string clears it).
    repo.set_photo_caption_new(person_id, repo.get_or_create_photo(photo_path), caption)
    return jsonify({"photo_captions": _person_photo_captions(repo, person_id)})


# ── Photo Metadata & Tagging ───────────────────────────────────────


@photos_bp.route("/api/photos/<int:photo_id>/metadata", methods=["PUT"])
@web_server.require_editor
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
    return jsonify(
        {
            "id": updated["id"],
            "file_path": updated["file_path"],
            "date": updated.get("date"),
            "date_circa": bool(updated.get("date_circa")),
            "place": updated.get("place"),
            "photo_type": updated.get("photo_type", "photo"),
            "lat": updated.get("lat"),
            "lng": updated.get("lng"),
        }
    )


@photos_bp.route("/api/photos/bulk-metadata", methods=["PUT"])
@web_server.require_editor
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


@photos_bp.route("/api/photos/reextract-exif", methods=["POST"])
@web_server.require_editor
def api_reextract_exif():
    """Bulk re-extract EXIF metadata for photos missing date and GPS.

    Fetches image bytes for each photo where lat IS NULL AND date IS NULL,
    runs EXIF extraction, and updates metadata.

    Returns {"updated": N}
    """
    from database.repository import _fetchall

    repo = TreeRepository()
    conn = get_connection()
    try:
        rows = _fetchall(
            conn, "SELECT id, file_path FROM photos WHERE lat IS NULL AND date IS NULL"
        )
    finally:
        conn.close()

    updated = 0
    for row in rows:
        file_path = row["file_path"]
        # Strip "photos/" prefix for storage lookup
        filename = (
            file_path.replace("photos/", "", 1) if file_path.startswith("photos/") else file_path
        )
        data = storage.photo_storage.get(filename)
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


@photos_bp.route("/api/people/<person_id>/profile-photo", methods=["PUT"])
@web_server.require_editor
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
    return jsonify({"ok": True, "photo_id": photo_id})


@photos_bp.route("/api/photos/<int:photo_id>/tag", methods=["POST"])
@web_server.require_editor
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
    return jsonify({"ok": True}), 201


@photos_bp.route("/api/photos/<int:photo_id>/tag/<person_id>", methods=["DELETE"])
@web_server.require_editor
def api_untag_person_from_photo(photo_id, person_id):
    """Remove a person's tag from a photo."""
    repo = TreeRepository()
    repo.unassign_photo_from_person(person_id, photo_id)
    return ("", 204)


# ── Face Regions ───────────────────────────────────────────────────────


@photos_bp.route("/api/photos/<int:photo_id>/face-region", methods=["PUT"])
@web_server.require_editor
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

    return jsonify(
        {
            "id": region_id,
            "photo_id": photo_id,
            "person_id": person_id,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "auto_tagged": person_id not in already_tagged,
        }
    )


@photos_bp.route("/api/photos/<int:photo_id>/face-regions")
def api_get_face_regions(photo_id):
    """Return all face regions for a photo."""
    repo = TreeRepository()
    regions = repo.get_face_regions(photo_id)
    return jsonify(
        [
            {
                "id": r["id"],
                "photo_id": r["photo_id"],
                "person_id": r["person_id"],
                "x": r["x"],
                "y": r["y"],
                "w": r["w"],
                "h": r["h"],
                "given_name": r.get("given_name", ""),
                "surname": r.get("surname", ""),
            }
            for r in regions
        ]
    )


@photos_bp.route("/api/photos/<int:photo_id>/face-region/<int:region_id>", methods=["DELETE"])
@web_server.require_editor
def api_delete_face_region(photo_id, region_id):
    """Delete a face region."""
    repo = TreeRepository()
    repo.delete_face_region(region_id)
    return ("", 204)


# ── Profile Crop ──────────────────────────────────────────────────────


@photos_bp.route("/api/people/<person_id>/profile-crop", methods=["PUT"])
@web_server.require_editor
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
        return jsonify(
            {"error": "crop coordinates must be in 0-1 range", "code": "bad_request"}
        ), 400
    if crop_x + crop_w > 1.001 or crop_y + crop_h > 1.001:
        return jsonify(
            {"error": "crop region extends beyond image bounds", "code": "bad_request"}
        ), 400

    repo = TreeRepository()
    person = repo.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    repo.set_profile_crop(person_id, int(photo_id), crop_x, crop_y, crop_w, crop_h)
    return jsonify(
        {
            "ok": True,
            "person_id": person_id,
            "photo_id": photo_id,
            "crop_x": crop_x,
            "crop_y": crop_y,
            "crop_w": crop_w,
            "crop_h": crop_h,
        }
    )


@photos_bp.route("/api/people/<person_id>/profile-crop", methods=["DELETE"])
@web_server.require_editor
def api_clear_profile_crop(person_id):
    """Clear the crop region for a person's profile photo."""
    body = request.get_json(force=True) or {}
    photo_id = body.get("photo_id")
    if not photo_id:
        return jsonify({"error": "photo_id required", "code": "missing_field"}), 400

    repo = TreeRepository()
    repo.clear_profile_crop(person_id, int(photo_id))
    return jsonify({"ok": True})
