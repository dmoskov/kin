"""Geocoding endpoint."""

from flask import Blueprint, jsonify, request

geocode_bp = Blueprint("geocode", __name__)


@geocode_bp.route("/api/geocode", methods=["POST"])
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
    return jsonify(
        {
            "coords": {p: list(c) for p, c in coords.items()},
            "pending": pending,
        }
    )
