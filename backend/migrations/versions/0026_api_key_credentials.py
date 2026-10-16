"""Forward frozen recovery DDL; historical rows retain authority.

Revision ID: 0026_api_key_credentials
Revises: 0025_graph_projection
"""

from alembic import op

revision = "0026_api_key_credentials"
down_revision = "0025_graph_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add only the approved fields, sidecars and integrity guards."""
    op.execute(
        """
CREATE TABLE api_keys (
    key_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    user_id TEXT NOT NULL,
    resource TEXT NOT NULL,
    scopes TEXT[] NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    version INTEGER NOT NULL,
    PRIMARY KEY (key_id),
    CONSTRAINT ck_api_keys_token_hash CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_api_keys_resource CHECK (resource = 'urn:dianzi:api:v1'),
    CONSTRAINT ck_api_keys_scopes CHECK (scopes = ARRAY['read:public']::text[] OR scopes =
ARRAY['read:asset']::text[] OR scopes = ARRAY['read:asset','read:public']::text[]),
    CONSTRAINT ck_api_keys_expiration CHECK (expires_at > issued_at AND expires_at <= issued_at +
INTERVAL '2160 hours'),
    CONSTRAINT ck_api_keys_revocation CHECK (revoked_at IS NULL OR revoked_at >= issued_at),
    CONSTRAINT ck_api_keys_version CHECK (version >= 1),
    UNIQUE (token_hash),
    FOREIGN KEY(user_id) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE api_key_rate_buckets (
    key_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    window_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    request_count INTEGER NOT NULL,
    PRIMARY KEY (key_id, operation, window_started_at),
    CONSTRAINT ck_api_key_rate_operation CHECK (operation IN ('read','ask')),
    CONSTRAINT ck_api_key_rate_window CHECK (window_started_at = date_trunc('minute',
window_started_at)),
    CONSTRAINT ck_api_key_rate_count CHECK (request_count >= 0 AND request_count <= CASE operation
WHEN 'read' THEN 60 ELSE 10 END),
    FOREIGN KEY(key_id) REFERENCES api_keys (key_id)
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_api_keys_user_id ON api_keys (user_id)
        """
    )


def downgrade() -> None:
    """Preserve receipts and revocation history; use approved forward repair."""
    raise RuntimeError("recovery history requires forward-only recovery")
