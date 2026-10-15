"""维度重试有独立发布键，保留0009旧行而不伪造其来源时点。

Revision ID: 0010_enrichment_publications
Revises: 0009_enrichment_results
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_enrichment_publications"
down_revision = "0009_enrichment_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """同输入失败后可发布成功尝试；旧行新增字段保持NULL未知。"""
    op.drop_constraint("uq_enrichment_result_input", "enrichment_results", type_="unique")
    for column in (
        sa.Column("publication_key", sa.Text()),
        sa.Column("payload_sha256", sa.Text()),
        sa.Column("event_version", sa.Integer()),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("source_version", sa.Text()),
        sa.Column("freshness", sa.Text()),
    ):
        op.add_column("enrichment_results", column)
    op.create_unique_constraint(
        "uq_enrichment_result_publication",
        "enrichment_results",
        ["event_id", "dimension", "publication_key"],
    )
    op.create_check_constraint(
        "ck_enrichment_publication_digest",
        "enrichment_results",
        "payload_sha256 IS NULL OR length(payload_sha256)=64",
    )
    op.create_check_constraint(
        "ck_enrichment_event_version",
        "enrichment_results",
        "event_version IS NULL OR event_version > 0",
    )
    op.create_check_constraint(
        "ck_enrichment_freshness",
        "enrichment_results",
        "freshness IS NULL OR freshness IN ('current','stale','unknown')",
    )


def downgrade() -> None:
    """重试产生的历史不能安全塞回旧唯一键；仅允许前向修复。"""
    raise RuntimeError("enrichment publication history requires forward-only recovery")
