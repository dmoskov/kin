"""Photo storage abstraction.

When ``S3_BUCKET`` is set in the environment, photos are stored in (and
served from) that S3 bucket.  Otherwise everything falls back to the
local ``private/photos/`` directory so that local development works
without any AWS credentials.

Usage::

    from storage import photo_storage

    # Upload
    photo_storage.put("1716234567-headshot.jpg", file_bytes)

    # Download
    data = photo_storage.get("1716234567-headshot.jpg")

    # Check existence
    if photo_storage.exists("1716234567-headshot.jpg"):
        ...

    # List all
    names = photo_storage.list_all()
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class PhotoStorage:
    """Abstract base for photo storage backends."""

    def put(self, filename: str, data: bytes) -> None:
        raise NotImplementedError

    def get(self, filename: str) -> bytes | None:
        raise NotImplementedError

    def exists(self, filename: str) -> bool:
        raise NotImplementedError

    def list_all(self) -> list[str]:
        raise NotImplementedError

    def delete(self, filename: str) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Local filesystem backend
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


class LocalStorage(PhotoStorage):
    """Read/write photos from one or more local directories.

    *write_dir* is where uploads are saved.  *read_dirs* are checked
    (in order) when fetching a photo — this lets us look in both
    ``private/photos/`` and ``web/photos/``.
    """

    def __init__(self, write_dir: Path, read_dirs: list[Path] | None = None):
        self.write_dir = write_dir
        self.read_dirs = read_dirs or [write_dir]

    def put(self, filename: str, data: bytes) -> None:
        self.write_dir.mkdir(parents=True, exist_ok=True)
        (self.write_dir / filename).write_bytes(data)

    def get(self, filename: str) -> bytes | None:
        for d in self.read_dirs:
            p = d / filename
            if p.is_file():
                return p.read_bytes()
        return None

    def exists(self, filename: str) -> bool:
        return any((d / filename).is_file() for d in self.read_dirs)

    def list_all(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for d in self.read_dirs:
            if not d.is_dir():
                continue
            for f in d.iterdir():
                if f.suffix.lower() in _IMAGE_EXTS and f.name not in seen:
                    seen.add(f.name)
                    result.append(f.name)
        return sorted(result)

    def delete(self, filename: str) -> None:
        for d in self.read_dirs:
            p = d / filename
            if p.is_file():
                p.unlink()
                return


# ---------------------------------------------------------------------------
# S3 backend
# ---------------------------------------------------------------------------


class S3Storage(PhotoStorage):
    """Store photos in an S3 bucket.

    Falls back to *local_fallback* for reads when a file isn't in S3
    (covers legacy photos that haven't been migrated yet).
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "photos/",
        local_fallback: LocalStorage | None = None,
    ):
        import boto3

        self.s3 = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix
        self.local = local_fallback

    def _key(self, filename: str) -> str:
        return f"{self.prefix}{filename}"

    def put(self, filename: str, data: bytes) -> None:
        import mimetypes

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self._key(filename),
            Body=data,
            ContentType=content_type,
        )
        logger.info("S3 put: s3://%s/%s (%d bytes)", self.bucket, self._key(filename), len(data))

    def get(self, filename: str) -> bytes | None:
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=self._key(filename))
            return resp["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            pass
        except Exception as e:
            logger.warning("S3 get failed for %s: %s", filename, e)
        # Fall back to local disk (legacy photos)
        if self.local:
            return self.local.get(filename)
        return None

    def exists(self, filename: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=self._key(filename))
            return True
        except Exception:
            pass
        if self.local:
            return self.local.exists(filename)
        return False

    def list_all(self) -> list[str]:
        names: set[str] = set()
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
                for obj in page.get("Contents", []):
                    name = obj["Key"].removeprefix(self.prefix)
                    if name:
                        names.add(name)
        except Exception as e:
            logger.warning("S3 list failed: %s", e)
        # Merge local photos too
        if self.local:
            names.update(self.local.list_all())
        return sorted(names)

    def delete(self, filename: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=self._key(filename))
        except Exception as e:
            logger.warning("S3 delete failed for %s: %s", filename, e)
        if self.local:
            self.local.delete(filename)


# ---------------------------------------------------------------------------
# Module-level singleton — import this
# ---------------------------------------------------------------------------


def init_storage(private_dir: Path | None = None, web_dir: Path | None = None) -> PhotoStorage:
    """Create the appropriate backend based on environment.

    Parameters can be overridden for testing.
    """
    if private_dir is None:
        project_root = Path(__file__).resolve().parent.parent
        private_dir = project_root / "private"
    if web_dir is None:
        project_root = Path(__file__).resolve().parent.parent
        web_dir = project_root / "web"

    private_photos = private_dir / "photos"
    web_photos = web_dir / "photos"
    local = LocalStorage(write_dir=private_photos, read_dirs=[private_photos, web_photos])

    bucket = os.environ.get("S3_BUCKET", "").strip()
    if bucket:
        logger.info("Using S3 storage: bucket=%s", bucket)
        return S3Storage(bucket=bucket, local_fallback=local)

    logger.info("Using local photo storage (no S3_BUCKET set)")
    return local


photo_storage: PhotoStorage = init_storage()
