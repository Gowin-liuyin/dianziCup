"""逐维结果与唯一知识PG库共享metadata；事实保留在原claims表。"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge import persistence_models as knowledge_models

enrichment_results = Table(
    "enrichment_results",
    knowledge_models.metadata,
    Column("result_id", Text(), primary_key=True),
    Column("event_id", Text(), ForeignKey("events.event_id"), nullable=False),
    Column("dimension", Text(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("claim_ids", JSONB(), nullable=False),
    Column("reference_ids", JSONB(), nullable=False),
    Column("error_code", Text()),
    Column("searched_at", DateTime(timezone=True)),
    Column("source_scope", JSONB(), nullable=False),
    Column("last_job_id", Text(), ForeignKey("job_runs.job_id")),
    Column("input_fingerprint", Text(), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("is_current", Boolean(), nullable=False),
)
