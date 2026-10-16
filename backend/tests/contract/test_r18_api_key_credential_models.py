"""Schema proposal contracts do not claim a production migration."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from ai_intel.api.credential_models import api_key_rate_buckets, api_keys


def test_only_hash_and_required_metadata_are_persisted() -> None:
    assert set(api_keys.c.keys()) == {
        "key_id",
        "token_hash",
        "user_id",
        "resource",
        "scopes",
        "issued_at",
        "expires_at",
        "revoked_at",
        "version",
    }
    assert set(api_key_rate_buckets.c.keys()) == {
        "key_id",
        "operation",
        "window_started_at",
        "request_count",
    }
    assert {column.name for column in api_key_rate_buckets.primary_key} == {
        "key_id",
        "operation",
        "window_started_at",
    }


def test_postgres_ddl_enforces_resource_expiry_scopes_and_count() -> None:
    key_ddl = str(CreateTable(api_keys).compile(dialect=postgresql.dialect()))
    bucket_ddl = str(CreateTable(api_key_rate_buckets).compile(dialect=postgresql.dialect()))
    for fragment in (
        "UNIQUE (token_hash)",
        "REFERENCES users (user_id)",
        "urn:dianzi:api:v1",
        "2160 hours",
        "read:public",
        "read:asset",
        "version >= 1",
    ):
        assert fragment in key_ddl
    for fragment in ("REFERENCES api_keys (key_id)", "60", "10", "request_count >= 0"):
        assert fragment in bucket_ddl
