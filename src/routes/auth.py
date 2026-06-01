"""Authentication endpoints."""

import json
import logging
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from flask import Blueprint, jsonify, request, session

import web_server
from database.connection import get_connection
from database.repository import TreeRepository, _execute, _ph

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def _get_google_client_id() -> str | None:
    """Get the Google Client ID from env or config file."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if client_id:
        return client_id
    # Fall back to family-config.json
    for candidate in [
        web_server.PRIVATE_DIR / "config" / "family-config.json",
        Path(web_server.WEB_DIR) / "family-config.json",
    ]:
        if candidate.exists():
            config = json.loads(candidate.read_text())
            if config.get("googleClientId"):
                return config["googleClientId"]
    return None


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


@auth_bp.route("/api/auth/google", methods=["POST"])
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
    is_editor = (not web_server.EDITORS) or (email in web_server.EDITORS)

    # Editors can sign in even without a person record in the tree.
    # Non-editors must have a matching person record (existing behaviour).
    repo = TreeRepository()
    person = repo.get_person_by_email(email)
    if not person and not is_editor:
        return jsonify(
            {
                "error": "No matching person record for this email",
                "email": email,
            }
        ), 403

    person_id = person.id if person else f"editor:{email}"
    full_name = person.full_name if person else payload.get("name", email)

    # Set session
    session["person_id"] = person_id
    session["email"] = email
    session["name"] = full_name
    session["picture"] = payload.get("picture", "")
    session["is_editor"] = is_editor

    return jsonify(
        {
            "person_id": person_id,
            "name": full_name,
            "email": email,
            "picture": payload.get("picture", ""),
            "is_editor": is_editor,
        }
    )


@auth_bp.route("/api/auth/me")
def api_auth_me():
    """Return the current logged-in user, or 401."""
    if "person_id" not in session:
        return jsonify({"error": "not authenticated"}), 401
    return jsonify(
        {
            "person_id": session["person_id"],
            "name": session.get("name", ""),
            "email": session.get("email", ""),
            "picture": session.get("picture", ""),
            "is_editor": session.get("is_editor", False),
        }
    )


@auth_bp.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Clear the session."""
    session.clear()
    return jsonify({"ok": True})


@auth_bp.route("/api/people/<person_id>/email", methods=["PUT"])
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
