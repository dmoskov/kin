"""Undo endpoints for reversing destructive actions.

Currently supports undoing person deletion (kind='delete_person').
The undo stack is persisted in the undo_log DB table so it works
correctly across multiple gunicorn workers.

Endpoints
---------
GET  /api/undo/status  — {"available": bool, "count": int}
POST /api/undo         — pop the latest entry and restore; returns
                         {"restored": "<kind>", "person_id": "...", "name": "..."}
                         or {"restored": null} when the stack is empty.
"""

import json

from flask import Blueprint, jsonify

import web_server
from database.repository import TreeRepository
from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, RelationshipType, Union, Visibility

undo_bp = Blueprint("undo", __name__)


# ── Status ──────────────────────────────────────────────────────────────


@undo_bp.route("/api/undo/status", methods=["GET"])
def api_undo_status():
    """Return whether undo is available and how many entries are queued."""
    repo = TreeRepository()
    count = repo.undo_count()
    return jsonify({"available": count > 0, "count": count})


# ── Undo ────────────────────────────────────────────────────────────────


@undo_bp.route("/api/undo", methods=["POST"])
@web_server.require_editor
def api_undo():
    """Pop the most recent undo entry and apply the reverse operation.

    Returns 200 with ``{"restored": null}`` when the stack is empty.
    Returns 200 with ``{"restored": "delete_person", "person_id": ..., "name": ...}``
    on success.
    """
    repo = TreeRepository()
    entry = repo.pop_undo()
    if entry is None:
        return jsonify({"restored": None})

    kind = entry["kind"]
    payload = entry["payload"]

    if kind == "delete_person":
        result = _restore_person(repo, payload)
        return jsonify(result)

    # Unknown kind — nothing to do but acknowledge.
    return jsonify({"restored": kind, "warning": "unrecognised undo kind"})


# ── Restore helpers ─────────────────────────────────────────────────────


def _restore_person(repo: TreeRepository, payload: dict) -> dict:
    """Re-create a person and all their snapshotted edges."""
    person_row = payload.get("person") or {}

    # Reconstruct the Person model from the raw row.
    person = Person(
        id=person_row["id"],
        given_name=person_row.get("given_name", ""),
        surname=person_row.get("surname", ""),
        gender=Gender(person_row.get("gender", "unknown")),
        birth_date=person_row.get("birth_date") or None,
        birth_place=person_row.get("birth_place") or None,
        death_date=person_row.get("death_date") or None,
        death_place=person_row.get("death_place") or None,
        maiden_name=person_row.get("maiden_name") or None,
        nicknames=json.loads(person_row.get("nicknames") or "[]"),
        notes=person_row.get("notes") or "",
        photo_paths=json.loads(person_row.get("photo_paths") or "[]"),
        photo_captions=json.loads(person_row.get("photo_captions") or "{}"),
        email=person_row.get("email") or None,
    )
    repo.save_person(person)

    # Restore parent-child relationships.
    for r in payload.get("relationships", []):
        rel = Relationship(
            parent_id=r["parent_id"],
            child_id=r["child_id"],
            rel_type=RelationshipType(r.get("rel_type", "biological")),
            visibility=Visibility(r.get("visibility", "everyone")),
        )
        repo.save_relationship(rel)

    # Restore unions.
    for u in payload.get("unions", []):
        union = Union(
            partner1_id=u["partner1_id"],
            partner2_id=u["partner2_id"],
            union_date=u.get("union_date") or None,
            union_place=u.get("union_place") or None,
            end_date=u.get("end_date") or None,
            end_reason=u.get("end_reason") or None,
            notes=u.get("notes") or "",
        )
        repo.save_union(union)

    # Restore events.
    for e in payload.get("events", []):
        event = LifeEvent(
            person_id=e["person_id"],
            event_type=EventType(e["event_type"]),
            date=e.get("date") or None,
            end_date=e.get("end_date") or None,
            place=e.get("place") or None,
            description=e.get("description") or "",
            source=e.get("source") or None,
            date_circa=bool(e.get("date_circa")),
        )
        repo.save_event(event)

    # Restore person_photos links (the photos rows themselves still exist).
    for pp in payload.get("person_photos", []):
        repo.assign_photo_to_person(
            person_id=pp["person_id"],
            photo_id=pp["photo_id"],
            caption=pp.get("caption") or "",
            display_order=pp.get("display_order") or 0,
            is_profile=bool(pp.get("is_profile")),
        )
        # Restore crop data if present.
        crop_x = pp.get("crop_x")
        if crop_x is not None:
            repo.set_profile_crop(
                person_id=pp["person_id"],
                photo_id=pp["photo_id"],
                crop_x=pp["crop_x"],
                crop_y=pp["crop_y"],
                crop_w=pp["crop_w"],
                crop_h=pp["crop_h"],
            )

    # Restore article links (the articles rows still exist).
    for pa in payload.get("person_articles", []):
        repo.link_article_to_person(
            person_id=pa["person_id"],
            article_id=pa["article_id"],
        )

    name_parts = [person.given_name, person.surname]
    name = " ".join(p for p in name_parts if p).strip() or person.id

    return {
        "restored": "delete_person",
        "person_id": person.id,
        "name": name,
    }
