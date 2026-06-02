"""Life-event CRUD endpoints (create, update, delete)."""

import re

from flask import Blueprint, jsonify, request

import web_server
from database.repository import TreeRepository
from models.event import EventType, LifeEvent

events_bp = Blueprint("events", __name__)

_VALID_EVENT_TYPES = {e.value for e in EventType}

_DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def _validate_event_payload(body: dict, *, require_person: bool) -> tuple[dict, str | None, int]:
    if not isinstance(body, dict):
        return {}, "body must be a JSON object", 400

    out: dict = {}

    if require_person:
        pid = (body.get("person_id") or "").strip()
        if not pid:
            return {}, "person_id is required", 400
        out["person_id"] = pid

    et = body.get("event_type")
    if et is not None:
        if et not in _VALID_EVENT_TYPES:
            return {}, f"event_type must be one of: {', '.join(sorted(_VALID_EVENT_TYPES))}", 400
        out["event_type"] = et

    for date_field in ("date", "end_date"):
        v = body.get(date_field)
        if v is not None:
            if isinstance(v, str):
                v = v.strip() or None
            if v and not _DATE_RE.match(v):
                return {}, f"{date_field} must be YYYY, YYYY-MM, or YYYY-MM-DD", 400
            out[date_field] = v

    for str_field in ("place", "description", "source"):
        if str_field in body:
            v = body[str_field]
            if isinstance(v, str):
                v = v.strip() or None
            out[str_field] = v

    if "date_circa" in body:
        out["date_circa"] = bool(body["date_circa"])

    return out, None, 0


@events_bp.route("/api/events", methods=["POST"])
@web_server.require_editor
def api_create_event():
    """Create a life event for a person.

    Body: {"person_id": "...", "event_type": "residence", "date": "1985",
           "end_date": "1992", "place": "Boston, MA", "description": "...",
           "date_circa": true}
    """
    body = request.get_json(silent=True) or {}
    fields, err, status = _validate_event_payload(body, require_person=True)
    if err:
        return jsonify({"error": err, "code": "bad_request"}), status

    if "event_type" not in fields:
        return jsonify({"error": "event_type is required", "code": "bad_request"}), 400

    repo = TreeRepository()
    if repo.get_person(fields["person_id"]) is None:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    event = LifeEvent(
        person_id=fields["person_id"],
        event_type=EventType(fields["event_type"]),
        date=fields.get("date"),
        end_date=fields.get("end_date"),
        place=fields.get("place"),
        description=fields.get("description") or "",
        source=fields.get("source"),
        date_circa=fields.get("date_circa", False),
    )
    event_id = repo.save_event_returning_id(event)
    result = {
        "id": event_id,
        "person_id": event.person_id,
        "event_type": event.event_type.value,
    }
    for key in ("date", "end_date", "place", "source"):
        val = getattr(event, key)
        if val is not None:
            result[key] = val
    if event.description:
        result["description"] = event.description
    if event.date_circa:
        result["date_circa"] = True
    return jsonify(result), 201


@events_bp.route("/api/events/<int:event_id>", methods=["PATCH"])
@web_server.require_editor
def api_update_event(event_id):
    """Update an existing life event."""
    body = request.get_json(silent=True) or {}
    fields, err, status = _validate_event_payload(body, require_person=False)
    if err:
        return jsonify({"error": err, "code": "bad_request"}), status

    repo = TreeRepository()
    existing = repo.get_event(event_id)
    if existing is None:
        return jsonify({"error": "event not found", "code": "not_found"}), 404

    updated = repo.update_event(event_id, **fields)
    if updated is None:
        return jsonify({"error": "no valid fields to update", "code": "bad_request"}), 400

    result = {
        "id": updated["id"],
        "person_id": updated["person_id"],
        "event_type": updated["event_type"],
    }
    for key in ("date", "end_date", "place", "source"):
        if updated.get(key) is not None:
            result[key] = updated[key]
    if updated.get("description"):
        result["description"] = updated["description"]
    if updated.get("date_circa"):
        result["date_circa"] = True
    return jsonify(result)


@events_bp.route("/api/events/<int:event_id>", methods=["DELETE"])
@web_server.require_editor
def api_delete_event(event_id):
    """Delete a life event."""
    repo = TreeRepository()
    existing = repo.get_event(event_id)
    if existing is None:
        return jsonify({"error": "event not found", "code": "not_found"}), 404

    repo.delete_event(event_id)
    return ("", 204)
