"""R18 table metadata proposal; production forward migration 0026 belongs to root."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY

from ai_intel.knowledge.models import metadata

api_keys = Table(
    "api_keys",
    metadata,
    Column("key_id", Text, primary_key=True),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("user_id", Text, ForeignKey("users.user_id"), nullable=False, index=True),
    Column("resource", Text, nullable=False),
    Column("scopes", ARRAY(Text), nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("version", Integer, nullable=False),
    CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_api_keys_token_hash"),
    CheckConstraint("resource = 'urn:dianzi:api:v1'", name="ck_api_keys_resource"),
    CheckConstraint(
        "scopes = ARRAY['read:public']::text[] "
        "OR scopes = ARRAY['read:asset']::text[] "
        "OR scopes = ARRAY['read:asset','read:public']::text[]",
        name="ck_api_keys_scopes",
    ),
    CheckConstraint(
        "expires_at > issued_at AND expires_at <= issued_at + INTERVAL '2160 hours'",
        name="ck_api_keys_expiration",
    ),
    CheckConstraint("revoked_at IS NULL OR revoked_at >= issued_at", name="ck_api_keys_revocation"),
    CheckConstraint("version >= 1", name="ck_api_keys_version"),
)

api_key_rate_buckets = Table(
    "api_key_rate_buckets",
    metadata,
    Column("key_id", Text, ForeignKey("api_keys.key_id"), primary_key=True),
    Column("operation", Text, primary_key=True),
    Column("window_started_at", DateTime(timezone=True), primary_key=True),
    Column("request_count", Integer, nullable=False),
    CheckConstraint("operation IN ('read','ask')", name="ck_api_key_rate_operation"),
    CheckConstraint(
        "window_started_at = date_trunc('minute', window_started_at)",
        name="ck_api_key_rate_window",
    ),
    CheckConstraint(
        "request_count >= 0 AND request_count <= CASE operation WHEN 'read' THEN 60 ELSE 10 END",
        name="ck_api_key_rate_count",
    ),
)
