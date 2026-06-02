"""Person CRUD and relationship/union creation endpoints."""

import json
import logging
import os
import re
import uuid

from flask import Blueprint, jsonify, request

import web_server
from database.repository import TreeRepository, _fetchall, _fetchone, _ph
from import_export.json_io import _event_to_dict, _person_to_dict
from models.person import Gender, Person

logger = logging.getLogger(__name__)

people_bp = Blueprint("people", __name__)


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
                return (
                    {},
                    (f"gender must be one of: {', '.join(sorted(_VALID_GENDERS))}"),
                    400,
                )
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


@people_bp.route("/api/people/search", methods=["GET"])
def api_search_people():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    repo = TreeRepository()
    results = repo.search_people(q)
    return jsonify([_person_to_dict(p) for p in results[:50]])


@people_bp.route("/api/people", methods=["POST"])
@web_server.require_editor
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
        return jsonify(
            {
                "error": f"person id already exists: {pid}",
                "code": "conflict",
            }
        ), 409

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


@people_bp.route("/api/people/<person_id>", methods=["PUT", "PATCH"])
@web_server.require_editor
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


def _snapshot_person(repo: TreeRepository, person_id: str) -> dict:
    """Gather all data needed to restore a person after deletion.

    Queries relationships, unions, events, person_photos and person_articles
    for the given person and returns a serialisable snapshot dict.
    """
    conn = repo._conn()
    try:
        p = _ph()
        person_row = _fetchone(conn, f"SELECT * FROM people WHERE id = {p}", (person_id,))
        relationships = _fetchall(
            conn,
            f"SELECT parent_id, child_id, rel_type, visibility FROM relationships WHERE parent_id = {p} OR child_id = {p}",
            (person_id, person_id),
        )
        unions = _fetchall(
            conn,
            f"""
            SELECT partner1_id, partner2_id, union_date, union_place,
                   end_date, end_reason, notes
            FROM unions
            WHERE partner1_id = {p} OR partner2_id = {p}
            """,
            (person_id, person_id),
        )
        events = _fetchall(
            conn,
            f"""
            SELECT person_id, event_type, date, end_date, place,
                   description, source
            FROM events WHERE person_id = {p}
            """,
            (person_id,),
        )
        person_photos = _fetchall(
            conn,
            f"""
            SELECT person_id, photo_id, is_profile, display_order,
                   caption, crop_x, crop_y, crop_w, crop_h
            FROM person_photos WHERE person_id = {p}
            """,
            (person_id,),
        )
        person_articles = _fetchall(
            conn,
            f"SELECT person_id, article_id FROM person_articles WHERE person_id = {p}",
            (person_id,),
        )
    finally:
        conn.close()

    return {
        "person": dict(person_row) if person_row else {},
        "relationships": [dict(r) for r in relationships],
        "unions": [dict(u) for u in unions],
        "events": [dict(e) for e in events],
        "person_photos": [dict(pp) for pp in person_photos],
        "person_articles": [dict(pa) for pa in person_articles],
    }


@people_bp.route("/api/people/<person_id>", methods=["DELETE"])
@web_server.require_editor
def api_delete_person(person_id):
    """Delete a person. Cascades to their relationships, unions, events,
    and citations via FK ON DELETE CASCADE (see schema).

    Snapshots the person and all their edges into undo_log before deletion
    so the action can be reversed via POST /api/undo.

    Returns 204 on success, 404 if the person didn't exist.
    """
    repo = TreeRepository()
    if repo.get_person(person_id) is None:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    # Snapshot everything before the CASCADE wipes it.
    snapshot = _snapshot_person(repo, person_id)
    repo.push_undo("delete_person", snapshot)

    # delete_person returns True if a row was actually deleted. We already
    # confirmed existence above, so a False here would indicate a race.
    ok = repo.delete_person(person_id)
    if not ok:
        return jsonify({"error": "delete failed", "code": "server_error"}), 500
    return ("", 204)


@people_bp.route("/api/people/<person_id>/summary", methods=["GET"])
def api_person_summary(person_id):
    """Generate an AI-powered biographical summary for a person.

    Gathers the person's data, family connections, and life events, then
    sends them to Claude Sonnet 4.6 to produce a concise narrative summary.

    Returns 200 with ``{"summary": "..."}`` on success, 404 if the person
    doesn't exist, 503 if the AI service is unavailable.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "AI service not configured", "code": "unavailable"}), 503

    repo = TreeRepository()
    tree = repo.load_tree()

    person = tree.people.get(person_id)
    if person is None:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    person_dict = _person_to_dict(person)

    parent_rels = [r for r in tree.relationships if r.child_id == person_id]
    child_rels = [r for r in tree.relationships if r.parent_id == person_id]
    unions = [u for u in tree.unions if u.partner1_id == person_id or u.partner2_id == person_id]
    events = sorted(
        [e for e in tree.events if e.person_id == person_id],
        key=lambda e: e.date or "",
    )

    def _name(pid):
        p = tree.people.get(pid)
        return p.full_name if p else pid

    family = {}
    if parent_rels:
        family["parents"] = [
            {"name": _name(r.parent_id), "rel_type": r.rel_type.value} for r in parent_rels
        ]
    if child_rels:
        family["children"] = [_name(r.child_id) for r in child_rels]
    if unions:
        family["partners"] = []
        for u in unions:
            partner_id = u.partner2_id if u.partner1_id == person_id else u.partner1_id
            entry = {"name": _name(partner_id)}
            if u.union_date:
                entry["married"] = u.union_date
            if u.end_date:
                entry["ended"] = u.end_date
                if u.end_reason:
                    entry["reason"] = u.end_reason
            family["partners"].append(entry)

    sibling_ids = set()
    for r in parent_rels:
        for cr in tree.relationships:
            if cr.parent_id == r.parent_id and cr.child_id != person_id:
                sibling_ids.add(cr.child_id)
    if sibling_ids:
        family["siblings"] = [_name(sid) for sid in sibling_ids]

    context = {
        "person": person_dict,
        "family": family,
        "life_events": [_event_to_dict(e) for e in events],
    }

    prompt = (
        "You are writing a brief biographical summary for a family tree profile page. "
        "Write 2-3 sentences that capture who this person is/was — their life dates, "
        "where they lived, their family connections, and any notable life events. "
        "Write in third person, in a warm but factual tone. "
        "If information is sparse, work with what you have and keep it shorter. "
        "Do NOT use bullet points or headers. Just flowing prose. "
        "Do NOT mention that information is limited or sparse. "
        "Return ONLY the summary text, no JSON or markup.\n\n"
        f"Person data:\n{json.dumps(context, indent=2)}"
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = message.content[0].text.strip()
        return jsonify({"summary": summary})
    except Exception:
        logger.exception("Failed to generate person summary")
        return jsonify({"error": "Failed to generate summary", "code": "ai_error"}), 500


@people_bp.route("/api/relationships", methods=["POST"])
@web_server.require_editor
def api_create_relationship():
    """Create a parent-child relationship.

    Body: {"parent_id": "...", "child_id": "..."}

    Returns 201 on success, 400 for missing fields, 404 if either person
    doesn't exist.
    """
    from models.relationship import Relationship, RelationshipType, Visibility

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

    try:
        rel_type = RelationshipType(body.get("rel_type", "biological"))
    except ValueError:
        rel_type = RelationshipType.BIOLOGICAL
    try:
        visibility = Visibility(body.get("visibility", "everyone"))
    except ValueError:
        visibility = Visibility.EVERYONE

    rel = Relationship(
        parent_id=parent_id,
        child_id=child_id,
        rel_type=rel_type,
        visibility=visibility,
    )
    repo.save_relationship(rel)
    repo.auto_link_siblings()
    return jsonify({"parent_id": parent_id, "child_id": child_id}), 201


@people_bp.route("/api/unions", methods=["POST"])
@web_server.require_editor
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
        return jsonify(
            {"error": "partner1_id and partner2_id are required", "code": "bad_request"}
        ), 400
    if p1 == p2:
        return jsonify(
            {"error": "partner1_id and partner2_id must differ", "code": "bad_request"}
        ), 400

    repo = TreeRepository()
    if repo.get_person(p1) is None:
        return jsonify({"error": f"person not found: {p1}", "code": "not_found"}), 404
    if repo.get_person(p2) is None:
        return jsonify({"error": f"person not found: {p2}", "code": "not_found"}), 404

    union_date = (body.get("union_date") or "").strip() or None
    union_place = (body.get("union_place") or "").strip() or None
    end_date = (body.get("end_date") or "").strip() or None
    end_reason = (body.get("end_reason") or "").strip() or None
    notes = (body.get("notes") or "").strip()

    union = Union(
        partner1_id=p1,
        partner2_id=p2,
        union_date=union_date,
        union_place=union_place,
        end_date=end_date,
        end_reason=end_reason,
        notes=notes,
    )
    repo.save_union(union)
    repo.auto_link_siblings()
    return jsonify({
        "partner1_id": p1,
        "partner2_id": p2,
        "union_date": union_date,
        "union_place": union_place,
        "end_date": end_date,
        "end_reason": end_reason,
    }), 201


@people_bp.route("/api/unions", methods=["PATCH"])
@web_server.require_editor
def api_update_union():
    """Update an existing union (e.g. to mark it as ended/divorced).

    Body: {"partner1_id": "...", "partner2_id": "...", ...fields to update...}
    Updatable fields: end_date, end_reason, union_date, union_place, notes.

    Returns 200 on success, 404 if the union doesn't exist.
    """
    body = request.get_json(silent=True) or {}
    p1 = (body.get("partner1_id") or "").strip()
    p2 = (body.get("partner2_id") or "").strip()
    if not p1 or not p2:
        return jsonify(
            {"error": "partner1_id and partner2_id are required", "code": "bad_request"}
        ), 400

    repo = TreeRepository()
    existing = repo.get_union(p1, p2)
    if not existing:
        return jsonify({"error": "union not found", "code": "not_found"}), 404

    kwargs = {}
    for field in ("end_date", "end_reason", "union_date", "union_place", "notes"):
        if field in body:
            val = body[field]
            if isinstance(val, str):
                val = val.strip() or None
            kwargs[field] = val

    repo.update_union(p1, p2, **kwargs)
    return jsonify({"ok": True})
