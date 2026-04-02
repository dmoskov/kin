"""Tiny web server for the family tree dashboard.

Serves static files from web/ and provides a single API endpoint
that returns the family tree data from the SQLite database.

Usage:
    python -m web_server [--port 8000]

Or via the CLI:
    python -m cli serve [--port 8000]
"""

import json
import os
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from database.connection import init_db
from database.repository import TreeRepository
from import_export.json_io import (
    _citation_to_dict,
    _event_to_dict,
    _person_to_dict,
    _rel_to_dict,
    _source_to_dict,
    _union_to_dict,
)


def _tree_to_json(repo: TreeRepository) -> str:
    """Load the tree from the DB and serialize to the JSON format the dashboard expects."""
    tree = repo.load_tree()
    data = {
        "people": [_person_to_dict(p) for p in tree.people.values()],
        "relationships": [_rel_to_dict(r) for r in tree.relationships],
        "unions": [_union_to_dict(u) for u in tree.unions],
        "events": [_event_to_dict(e) for e in tree.events],
        "sources": [_source_to_dict(s) for s in tree.sources.values()],
        "citations": [_citation_to_dict(c) for c in tree.citations],
    }
    return json.dumps(data, ensure_ascii=False)


class FamilyTreeHandler(SimpleHTTPRequestHandler):
    """Serve static files from web/ and handle /api/data from the DB."""

    def __init__(self, *args, repo: TreeRepository, **kwargs):
        self._repo = repo
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/api/data":
            body = _tree_to_json(self._repo).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, format, *args):
        # Quieter logging — skip noisy static-file requests
        if "/api/" in (args[0] if args else ""):
            super().log_message(format, *args)


def serve(port: int = 8000) -> None:
    """Start the web server."""
    # Resolve web/ directory (relative to this file → ../web/)
    web_dir = str(Path(__file__).resolve().parent.parent / "web")
    if not Path(web_dir).is_dir():
        print(f"Error: web directory not found at {web_dir}")
        return

    # Ensure DB is initialized
    init_db()
    repo = TreeRepository()

    # Change to web/ so SimpleHTTPRequestHandler serves files from there
    os.chdir(web_dir)

    handler = partial(FamilyTreeHandler, repo=repo)
    server = HTTPServer(("", port), handler)

    print(f"\n  Family Tree Dashboard")
    print(f"  http://localhost:{port}")
    print(f"  API: http://localhost:{port}/api/data")
    print(f"\n  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Family Tree web server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()
    serve(args.port)
