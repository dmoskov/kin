"""Tests for the photo storage abstraction (LocalStorage, S3Storage, init_storage)."""

from unittest.mock import MagicMock, patch

import pytest

from storage import LocalStorage, S3Storage, init_storage


# ── LocalStorage ──────────────────────────────────────────────────────


class TestLocalStorage:
    @pytest.fixture
    def store(self, tmp_path):
        write_dir = tmp_path / "photos"
        return LocalStorage(write_dir=write_dir)

    def test_put_creates_dir_and_file(self, store):
        store.put("test.jpg", b"\xff\xd8data")
        assert (store.write_dir / "test.jpg").read_bytes() == b"\xff\xd8data"

    def test_get_returns_file_contents(self, store):
        store.put("a.jpg", b"img")
        assert store.get("a.jpg") == b"img"

    def test_get_missing_returns_none(self, store):
        assert store.get("nope.jpg") is None

    def test_exists_true_and_false(self, store):
        store.put("yes.jpg", b"x")
        assert store.exists("yes.jpg") is True
        assert store.exists("no.jpg") is False

    def test_delete_removes_file(self, store):
        store.put("del.jpg", b"x")
        store.delete("del.jpg")
        assert store.exists("del.jpg") is False

    def test_delete_nonexistent_is_noop(self, store):
        store.delete("ghost.jpg")

    def test_list_all_returns_image_files_sorted(self, store):
        store.put("b.jpg", b"x")
        store.put("a.png", b"x")
        store.put("c.txt", b"x")  # not an image ext
        names = store.list_all()
        assert names == ["a.png", "b.jpg"]

    def test_multiple_read_dirs(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "photo1.jpg").write_bytes(b"from_a")
        (dir_b / "photo2.jpg").write_bytes(b"from_b")

        store = LocalStorage(write_dir=dir_a, read_dirs=[dir_a, dir_b])
        assert store.get("photo1.jpg") == b"from_a"
        assert store.get("photo2.jpg") == b"from_b"
        assert store.exists("photo2.jpg") is True
        assert sorted(store.list_all()) == ["photo1.jpg", "photo2.jpg"]

    def test_list_all_deduplicates_across_dirs(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "same.jpg").write_bytes(b"a")
        (dir_b / "same.jpg").write_bytes(b"b")

        store = LocalStorage(write_dir=dir_a, read_dirs=[dir_a, dir_b])
        assert store.list_all() == ["same.jpg"]

    def test_get_prefers_first_read_dir(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "x.jpg").write_bytes(b"first")
        (dir_b / "x.jpg").write_bytes(b"second")

        store = LocalStorage(write_dir=dir_a, read_dirs=[dir_a, dir_b])
        assert store.get("x.jpg") == b"first"


# ── S3Storage ─────────────────────────────────────────────────────────


class TestS3Storage:
    @pytest.fixture
    def mock_s3(self):
        mock_boto = MagicMock()
        client = MagicMock()
        mock_boto.client.return_value = client
        with patch.dict("sys.modules", {"boto3": mock_boto}):
            yield client

    @pytest.fixture
    def store(self, mock_s3):
        return S3Storage(bucket="test-bucket", prefix="photos/")

    def test_put_calls_s3(self, store, mock_s3):
        store.put("img.jpg", b"data")
        mock_s3.put_object.assert_called_once()
        call_kw = mock_s3.put_object.call_args
        assert call_kw.kwargs["Bucket"] == "test-bucket"
        assert call_kw.kwargs["Key"] == "photos/img.jpg"
        assert call_kw.kwargs["Body"] == b"data"

    def test_get_returns_body(self, store, mock_s3):
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"s3data")}
        assert store.get("img.jpg") == b"s3data"

    def test_get_falls_back_to_local(self, mock_s3, tmp_path):
        no_such_key = type("NoSuchKey", (Exception,), {})
        mock_s3.exceptions.NoSuchKey = no_such_key
        mock_s3.get_object.side_effect = no_such_key("not found")
        local = LocalStorage(write_dir=tmp_path)
        local.put("fallback.jpg", b"local")
        store = S3Storage(bucket="b", local_fallback=local)
        assert store.get("fallback.jpg") == b"local"

    def test_get_returns_none_without_fallback(self, store, mock_s3):
        no_such_key = type("NoSuchKey", (Exception,), {})
        mock_s3.exceptions.NoSuchKey = no_such_key
        mock_s3.get_object.side_effect = no_such_key("not found")
        assert store.get("nope.jpg") is None

    def test_exists_true_via_head(self, store, mock_s3):
        mock_s3.head_object.return_value = {}
        assert store.exists("img.jpg") is True

    def test_exists_false_falls_back(self, mock_s3, tmp_path):
        mock_s3.head_object.side_effect = Exception("404")
        local = LocalStorage(write_dir=tmp_path)
        store = S3Storage(bucket="b", local_fallback=local)
        assert store.exists("nope.jpg") is False

    def test_delete_calls_s3_and_local(self, mock_s3, tmp_path):
        local = LocalStorage(write_dir=tmp_path)
        local.put("del.jpg", b"x")
        store = S3Storage(bucket="b", local_fallback=local)
        store.delete("del.jpg")
        mock_s3.delete_object.assert_called_once()
        assert not local.exists("del.jpg")

    def test_list_all_merges_s3_and_local(self, mock_s3, tmp_path):
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Contents": [{"Key": "photos/s3.jpg"}]}]
        mock_s3.get_paginator.return_value = paginator

        local = LocalStorage(write_dir=tmp_path)
        local.put("local.jpg", b"x")
        store = S3Storage(bucket="b", prefix="photos/", local_fallback=local)
        assert store.list_all() == ["local.jpg", "s3.jpg"]

    def test_key_prefix(self, mock_s3):
        store = S3Storage(bucket="b", prefix="img/")
        assert store._key("photo.jpg") == "img/photo.jpg"


# ── init_storage ──────────────────────────────────────────────────────


class TestInitStorage:
    def test_returns_local_without_s3_bucket(self, tmp_path, monkeypatch):
        monkeypatch.delenv("S3_BUCKET", raising=False)
        store = init_storage(private_dir=tmp_path, web_dir=tmp_path / "web")
        assert isinstance(store, LocalStorage)

    def test_returns_s3_with_bucket(self, tmp_path, monkeypatch):
        monkeypatch.setenv("S3_BUCKET", "my-bucket")
        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            store = init_storage(private_dir=tmp_path, web_dir=tmp_path / "web")
        assert isinstance(store, S3Storage)
