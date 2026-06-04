"""Flask blueprints for family tree API routes."""

from routes.articles import articles_bp
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.events import events_bp
from routes.export import export_bp
from routes.geocode import geocode_bp
from routes.people import people_bp
from routes.photos import photos_bp
from routes.undo import undo_bp
from routes.wikipedia import wikipedia_bp

ALL_BLUEPRINTS = [
    auth_bp,
    people_bp,
    photos_bp,
    documents_bp,
    geocode_bp,
    articles_bp,
    events_bp,
    export_bp,
    undo_bp,
    wikipedia_bp,
]
