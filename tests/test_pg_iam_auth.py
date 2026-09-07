"""RDS IAM auth: a passwordless DATABASE_URL mints a token at connect time."""

import sys
import types

import pytest

pytest.importorskip("psycopg2")

from database import connection  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_token_cache():
    connection._IAM_TOKEN_CACHE.clear()
    yield
    connection._IAM_TOKEN_CACHE.clear()


@pytest.fixture
def fake_boto3(monkeypatch):
    calls = []

    class _Rds:
        def __init__(self, region_name):
            self.region_name = region_name

        def generate_db_auth_token(self, **kw):
            calls.append((self.region_name, kw))
            return "iam-token"

    mod = types.SimpleNamespace(client=lambda svc, region_name: _Rds(region_name))
    monkeypatch.setitem(sys.modules, "boto3", mod)
    return calls


@pytest.fixture
def fake_connect(monkeypatch):
    import psycopg2

    seen = {}

    def _connect(dsn, **kwargs):
        seen["dsn"], seen["kwargs"] = dsn, kwargs

        class _Conn:
            autocommit = True

        return _Conn()

    monkeypatch.setattr(psycopg2, "connect", _connect)
    return seen


HOST = "familytree-db.abc123.us-east-1.rds.amazonaws.com"


def test_passwordless_dsn_uses_iam_token(monkeypatch, fake_boto3, fake_connect):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"postgresql://familytree_app@{HOST}:5432/familytree")

    connection._get_pg_connection()

    assert fake_boto3 == [
        ("us-east-1", {"DBHostname": HOST, "Port": 5432,
                       "DBUsername": "familytree_app", "Region": "us-east-1"})
    ]
    assert fake_connect["kwargs"]["password"] == "iam-token"
    assert fake_connect["kwargs"]["sslmode"] == "require"


def test_explicit_sslmode_is_kept(monkeypatch, fake_boto3, fake_connect):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv(
        "DATABASE_URL", f"postgresql://familytree_app@{HOST}/familytree?sslmode=verify-full"
    )
    connection._get_pg_connection()
    assert "sslmode" not in fake_connect["kwargs"]  # DSN's verify-full wins


def test_dsn_with_password_skips_iam(monkeypatch, fake_boto3, fake_connect):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secret@localhost:5432/familytree")
    connection._get_pg_connection()
    assert fake_boto3 == []
    assert "password" not in fake_connect["kwargs"]


def test_unknown_region_fails_loudly(monkeypatch, fake_boto3, fake_connect):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@db.internal:5432/familytree")
    with pytest.raises(RuntimeError, match="AWS_REGION"):
        connection._get_pg_connection()


def test_token_is_cached_until_ttl(monkeypatch, fake_boto3, fake_connect):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("DATABASE_URL", f"postgresql://familytree_app@{HOST}/familytree")
    clock = [1000.0]
    monkeypatch.setattr(connection.time, "monotonic", lambda: clock[0])

    connection._get_pg_connection()
    connection._get_pg_connection()
    assert len(fake_boto3) == 1  # second connect reused the token

    clock[0] += connection._IAM_TOKEN_TTL_SECONDS + 1
    connection._get_pg_connection()
    assert len(fake_boto3) == 2  # expired → minted again
