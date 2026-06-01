"""Tests for upload + photo-association endpoints in web_server.

Covers:
  - Photo upload happy path and hardening (size cap, magic bytes, type check).
  - Photo association (attach/detach/caption) via TreeRepository — the
    production PostgreSQL regression fix. A regression guard test exercises
    exactly the code path that previously used raw SQLite ``?`` placeholders.
  - Document upload hardening (size cap, magic bytes, cleanup on DB failure).
  - Filename sanitization for path traversal and empty slugs.

All tests use a temporary SQLite database and the Flask test client, so
they're hermetic and fast.
"""

from __future__ import annotations

import io
import struct
import zlib

import pytest

from models.person import Gender, Person

# ── PNG / JPG / GIF / WEBP byte helpers ──────────────────────────────────


def _tiny_png() -> bytes:
    """Return the bytes of a minimal valid 1x1 PNG."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    # 1x1 RGB pixel, filtered, zlib-compressed
    raw = b"\x00\xff\x00\x00"  # filter byte + RGB
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _tiny_jpeg() -> bytes:
    """Return bytes with the JPEG magic prefix (enough for imghdr)."""
    # imghdr.what() only needs the first few bytes to be JPEG-like.
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64 + b"\xff\xd9"


def _tiny_gif() -> bytes:
    return b"GIF89a" + b"\x00" * 32


def _tiny_webp() -> bytes:
    # RIFF....WEBPVP8 ...
    body = b"WEBPVP8 " + b"\x00" * 32
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _tiny_pdf() -> bytes:
    return b"%PDF-1.4\n%%EOF\n"


def _not_an_image() -> bytes:
    return b"MZ" + b"\x00" * 128  # Windows PE magic — definitely not an image


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Return a (flask_client, repo, db_path) triple.

    Creates a fresh SQLite DB + redirects the web_server's PRIVATE_DIR to
    tmp_path so uploaded files don't pollute the real private/ directory.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)

    from database.connection import init_db

    init_db(db_path)

    # Import after env is set so the module picks it up, and redirect
    # PRIVATE_DIR to tmp_path.
    import importlib

    import web_server

    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True

    # Reinitialize photo storage to use the tmp_path
    import storage

    storage.photo_storage = storage.init_storage(private_dir=tmp_path, web_dir=tmp_path / "web")
    web_server.photo_storage = storage.photo_storage

    from database.repository import TreeRepository

    repo = TreeRepository(db_path)

    # Seed a person.
    repo.save_person(
        Person(
            id="p1",
            given_name="Alice",
            surname="Test",
            gender=Gender.FEMALE,
        )
    )

    with web_server.app.test_client() as client:
        yield client, repo, tmp_path


# ── Photo upload ─────────────────────────────────────────────────────────


class TestPhotoUpload:
    def test_happy_path_png(self, app_client):
        client, _repo, tmp = app_client
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(_tiny_png()), "vacation.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["path"].startswith("photos/")
        assert body["path"].endswith(".png")
        # File actually exists.
        assert (tmp / body["path"]).exists()

    def test_happy_path_jpeg(self, app_client):
        client, _repo, _tmp = app_client
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(_tiny_jpeg()), "IMG_1234.JPG")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert resp.get_json()["path"].endswith(".jpg")

    def test_missing_file(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/photos/upload", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "missing_file"

    def test_empty_filename(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(_tiny_png()), "")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        # Flask treats empty filename as missing_file at the werkzeug layer.
        assert resp.get_json()["code"] in {"missing_file", "empty_filename"}

    def test_rejects_disallowed_extension(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(b"#!/bin/sh\necho bad"), "evil.sh")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["code"] == "invalid_type"
        assert ".sh" in body["error"]

    def test_rejects_empty_file(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(b""), "empty.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "empty"

    def test_rejects_oversize(self, app_client, monkeypatch):
        import web_server

        monkeypatch.setattr(web_server, "MAX_PHOTO_BYTES", 1024)  # 1 KB
        client, _, _ = app_client
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4096
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(big), "big.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 413
        assert resp.get_json()["code"] == "too_large"

    def test_rejects_mismatched_content(self, app_client, tmp_path):
        """File named .jpg but containing non-image bytes is rejected and removed."""
        client, _, tmp = app_client
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(_not_an_image()), "fake.jpg")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_content"
        # No orphan file left behind.
        photo_dir = tmp / "photos"
        if photo_dir.exists():
            assert list(photo_dir.iterdir()) == []

    def test_sanitizes_path_traversal(self, app_client):
        client, _, tmp = app_client
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(_tiny_png()), "../../etc/passwd.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        path = resp.get_json()["path"]
        # Output must be under photos/ and must not contain ..
        assert path.startswith("photos/")
        assert ".." not in path
        assert (tmp / path).exists()


# ── Photo association (the production PG regression fix) ─────────────────


class TestPhotoAssociation:
    """These endpoints previously used raw SQLite syntax and broke silently
    on PostgreSQL. They now go through TreeRepository. The tests exercise the
    exact code path — so if someone re-introduces raw SQL with ``?``
    placeholders (or anything backend-specific), these tests will still pass
    on SQLite but at least the happy-path coverage is there."""

    def test_attach_photo(self, app_client):
        client, repo, _ = app_client
        resp = client.post(
            "/api/people/p1/photos",
            json={"photo_paths": ["photos/a.jpg"]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["photo_paths"] == ["photos/a.jpg"]
        # Round-trip through the repository.
        assert repo.get_person("p1").photo_paths == ["photos/a.jpg"]

    def test_attach_is_idempotent(self, app_client):
        client, repo, _ = app_client
        client.post("/api/people/p1/photos", json={"photo_paths": ["photos/a.jpg"]})
        resp = client.post(
            "/api/people/p1/photos",
            json={"photo_paths": ["photos/a.jpg", "photos/b.jpg"]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["photo_paths"] == ["photos/a.jpg", "photos/b.jpg"]
        assert repo.get_person("p1").photo_paths == ["photos/a.jpg", "photos/b.jpg"]

    def test_attach_unknown_person_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people/nope/photos", json={"photo_paths": ["photos/a.jpg"]})
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_attach_requires_photo_paths(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people/p1/photos", json={})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "missing_field"

    def test_attach_rejects_non_list(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people/p1/photos", json={"photo_paths": "photos/a.jpg"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_type"

    def test_detach_photo(self, app_client):
        client, repo, _ = app_client
        client.post("/api/people/p1/photos", json={"photo_paths": ["photos/a.jpg", "photos/b.jpg"]})
        resp = client.delete("/api/people/p1/photos", json={"photo_path": "photos/a.jpg"})
        assert resp.status_code == 200
        assert resp.get_json()["photo_paths"] == ["photos/b.jpg"]
        assert repo.get_person("p1").photo_paths == ["photos/b.jpg"]

    def test_detach_drops_caption(self, app_client):
        client, repo, _ = app_client
        client.post("/api/people/p1/photos", json={"photo_paths": ["photos/a.jpg"]})
        client.put(
            "/api/people/p1/photo-caption",
            json={"photo_path": "photos/a.jpg", "caption": "Easter 1987"},
        )
        assert repo.get_person("p1").photo_captions == {"photos/a.jpg": "Easter 1987"}
        client.delete("/api/people/p1/photos", json={"photo_path": "photos/a.jpg"})
        # Caption should be cleaned up along with the photo.
        assert repo.get_person("p1").photo_captions == {}

    def test_detach_unknown_person(self, app_client):
        client, _, _ = app_client
        resp = client.delete("/api/people/nope/photos", json={"photo_path": "photos/a.jpg"})
        assert resp.status_code == 404

    def test_detach_requires_photo_path(self, app_client):
        client, _, _ = app_client
        resp = client.delete("/api/people/p1/photos", json={})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "missing_field"

    def test_set_caption(self, app_client):
        client, repo, _ = app_client
        client.post("/api/people/p1/photos", json={"photo_paths": ["photos/a.jpg"]})
        resp = client.put(
            "/api/people/p1/photo-caption",
            json={"photo_path": "photos/a.jpg", "caption": "  Easter 1987  "},
        )
        assert resp.status_code == 200
        # Trimmed.
        assert resp.get_json()["photo_captions"] == {"photos/a.jpg": "Easter 1987"}
        assert repo.get_person("p1").photo_captions == {"photos/a.jpg": "Easter 1987"}

    def test_empty_caption_clears(self, app_client):
        client, repo, _ = app_client
        client.post("/api/people/p1/photos", json={"photo_paths": ["photos/a.jpg"]})
        client.put(
            "/api/people/p1/photo-caption",
            json={"photo_path": "photos/a.jpg", "caption": "Something"},
        )
        resp = client.put(
            "/api/people/p1/photo-caption",
            json={"photo_path": "photos/a.jpg", "caption": ""},
        )
        assert resp.status_code == 200
        assert resp.get_json()["photo_captions"] == {}
        assert repo.get_person("p1").photo_captions == {}

    def test_caption_unknown_person(self, app_client):
        client, _, _ = app_client
        resp = client.put(
            "/api/people/nope/photo-caption",
            json={"photo_path": "photos/a.jpg", "caption": "x"},
        )
        assert resp.status_code == 404

    def test_does_not_use_raw_sqlite_placeholders(self):
        """Regression guard: source code must not use raw ``conn.execute``
        with '?' placeholders in the photo-association endpoints. Those only
        work on SQLite and silently break in production PostgreSQL."""
        import inspect

        from routes.photos import api_add_photos, api_remove_photo, api_set_photo_caption

        for name, fn in [
            ("api_add_photos", api_add_photos),
            ("api_remove_photo", api_remove_photo),
            ("api_set_photo_caption", api_set_photo_caption),
        ]:
            src = inspect.getsource(fn)
            assert "conn.execute(" not in src, (
                f"{name} uses raw conn.execute — must go through TreeRepository"
            )


# ── Document upload ──────────────────────────────────────────────────────


class TestDocumentUpload:
    def test_happy_path_pdf(self, app_client):
        client, _, tmp = app_client
        resp = client.post(
            "/api/documents/upload",
            data={"file": (io.BytesIO(_tiny_pdf()), "cert.pdf")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["file_type"] == "pdf"
        assert body["status"] == "uploaded"
        assert body["document_id"]

    def test_happy_path_image(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/documents/upload",
            data={"file": (io.BytesIO(_tiny_png()), "scan.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert resp.get_json()["file_type"] == "image"

    def test_rejects_disallowed_extension(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/documents/upload",
            data={"file": (io.BytesIO(b"zip stuff"), "archive.zip")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "invalid_type"

    def test_rejects_mismatched_pdf(self, app_client):
        client, _, tmp = app_client
        resp = client.post(
            "/api/documents/upload",
            data={"file": (io.BytesIO(b"not really a pdf"), "fake.pdf")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_content"
        # No file left on disk.
        doc_dir = tmp / "documents"
        if doc_dir.exists():
            assert list(doc_dir.iterdir()) == []

    def test_rejects_oversize(self, app_client, monkeypatch):
        import web_server

        monkeypatch.setattr(web_server, "MAX_DOC_BYTES", 512)
        client, _, _ = app_client
        resp = client.post(
            "/api/documents/upload",
            data={"file": (io.BytesIO(b"%PDF-" + b"\x00" * 4096), "big.pdf")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 413
        assert resp.get_json()["code"] == "too_large"


# ── Filename sanitization unit tests ─────────────────────────────────────


class TestSanitizeFilename:
    def test_strips_traversal(self):
        from web_server import _sanitize_filename

        out = _sanitize_filename("../../etc/passwd.png")
        assert ".." not in out
        assert out.endswith(".png")

    def test_strips_nul_bytes(self):
        from web_server import _sanitize_filename

        out = _sanitize_filename("bad\x00name.png")
        assert "\x00" not in out

    def test_fallback_for_empty_stem(self):
        from web_server import _sanitize_filename

        out = _sanitize_filename("___.png")
        assert "upload" in out
        assert out.endswith(".png")

    def test_lowercases_extension(self):
        from web_server import _sanitize_filename

        out = _sanitize_filename("Photo.JPG")
        assert out.endswith(".jpg")

    def test_slugifies_spaces_and_symbols(self):
        from web_server import _sanitize_filename

        out = _sanitize_filename("My Great Photo!.png")
        assert "my-great-photo" in out
        assert "!" not in out
        assert " " not in out


# ── 413 JSON error handler ───────────────────────────────────────────────


class TestOversizeHandler:
    def test_413_returns_json(self, app_client, monkeypatch):
        """Flask-level MAX_CONTENT_LENGTH aborts should return JSON, not HTML."""
        import web_server

        # Set MAX_CONTENT_LENGTH to something tiny.
        client, _, _ = app_client
        web_server.app.config["MAX_CONTENT_LENGTH"] = 10
        resp = client.post(
            "/api/photos/upload",
            data={"photo": (io.BytesIO(b"\x00" * 10000), "x.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 413
        body = resp.get_json()
        assert body is not None
        assert body["code"] == "too_large"
