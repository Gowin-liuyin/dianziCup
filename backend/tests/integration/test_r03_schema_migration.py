"""真实隔离PG迁移后的任务交付与游标映射，读取而不清理共享业务。"""

from sqlalchemy import inspect

from ai_intel.knowledge import models


def test_job_payload_history_and_cursor_columns_match_real_schema(migrated_engine):
    inspector = inspect(migrated_engine)
    for table_name in (
        "job_runs",
        "outbox_events",
        "job_payloads",
        "job_transitions",
        "source_cursors",
        "source_page_receipts",
    ):
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        assert actual == set(getattr(models, table_name).c.keys()), table_name
    unique_indexes = inspector.get_indexes("job_runs")
    assert any(
        index["name"] == "uq_job_scoped_idempotency" and index["unique"] for index in unique_indexes
    )
