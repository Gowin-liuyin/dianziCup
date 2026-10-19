"""Use frozen reflection assertions on the independently upgraded database only."""

import importlib.util
import json
import os

import pytest
from review_runner import DATABASE_PREFIX, ROOT, RUN
from sqlalchemy import create_engine, text

SOURCE = ROOT / "backend/tests/integration/test_r11_r08_forward_migration_schema.py"
SPEC = importlib.util.spec_from_file_location("frozen_migration_reflection_review", SOURCE)
ORIGINAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORIGINAL)
ORIGINAL.RUN = RUN
metadata_reference_schema = ORIGINAL.metadata_reference_schema
test_every_column_key_check_index_matches_frozen_metadata = (
    ORIGINAL.test_every_column_key_check_index_matches_frozen_metadata
)
test_exact_trigger_body_and_timing_match_frozen_metadata = (
    ORIGINAL.test_exact_trigger_body_and_timing_match_frozen_metadata
)
test_repeated_upgrade_head_is_non_destructive = (
    ORIGINAL.test_repeated_upgrade_head_is_non_destructive
)


@pytest.fixture(scope="module")
def schema_engine():
    engine = create_engine(os.environ["TEST_DATABASE_URL"], hide_parameters=True)
    assert engine.url.database == DATABASE_PREFIX + "_fresh"
    assert engine.url.host == "127.0.0.1" and engine.url.port == 25432
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == engine.url.database
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ORIGINAL.HEAD
    yield engine
    engine.dispose()


def test_independent_37_old_tables_preserve_exact_rows_and_hashes():
    before = json.loads((RUN / "history_before_0016.json").read_text())
    after = json.loads((RUN / "history_after_0019.json").read_text())
    assert before == after
    assert len(before) == 37
    assert before["job_transitions"]["row_count"] == 2
    for table_name in (
        "sources",
        "documents",
        "document_revisions",
        "content_objects",
        "text_blocks",
        "evidence",
        "claims",
        "claim_evidence",
        "users",
        "events",
        "job_runs",
        "job_payloads",
        "outbox_events",
        "source_cursors",
    ):
        assert before[table_name]["row_count"] == 1
