"""Offline query boundary checks use explicit recording fixtures, never PG or broker."""

from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql

from ai_intel.infrastructure.outbox import relay_pending_events


def test_relay_selection_requires_authority_and_locks_before_publication():
    captured = []

    class EmptyRows:
        def mappings(self):
            return self

        def all(self):
            return []

    class RecordingSession:
        def execute(self, statement):
            captured.append(statement)
            return EmptyRows()

    sent = []
    assert relay_pending_events(RecordingSession(), datetime.now(UTC), publisher=sent.append) == []
    compiled = captured[0].compile(
        dialect=postgresql.dialect(), compile_kwargs={"render_postcompile": True}
    )
    sql = str(compiled)
    assert "JOIN job_runs ON job_runs.job_id = outbox_events.job_id" in sql
    assert "outbox_events.payload_ref = job_runs.payload_ref" in sql
    assert "FOR UPDATE OF job_runs, outbox_events SKIP LOCKED" in sql
    assert {"queued", "retry_wait", "running"}.issubset(set(compiled.params.values()))
    assert "job_runs.status IN" in sql and sql.index("job_runs.status IN") < sql.index("LIMIT")
    assert sent == []
