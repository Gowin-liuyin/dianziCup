"""Terminal constraint checking follows complete writes and preserves legacy callers."""

import time
from contextlib import nullcontext

import pytest

from ai_intel.retrieval import indexing


@pytest.mark.parametrize("bounded", (False, True))
def test_projection_transaction_finishes_pending_writes_before_constraint_check(
    monkeypatch, bounded
):
    observed = []

    class FixtureSession:
        def __enter__(self):
            return self

        def __exit__(self, *arguments):
            pass

        def flush(self):
            observed.append("pending_writes_finished")

        def execute(self, statement):
            observed.append(str(statement))

        def commit(self):
            observed.append("commit")

        def rollback(self):
            observed.append("rollback")

    class FixtureEngine:
        def connect(self):
            return nullcontext(object())

    monkeypatch.setattr(indexing, "Session", lambda connection: FixtureSession())
    monkeypatch.setattr(indexing, "projection_database_deadline", lambda *arguments: nullcontext())
    monkeypatch.setattr(indexing.event, "listen", lambda *arguments: None)
    monkeypatch.setattr(indexing.event, "remove", lambda *arguments: None)
    with indexing._projection_session(FixtureEngine(), time.monotonic() + 1 if bounded else None):
        observed.append("business_writes")
    assert observed == (
        ["business_writes", "pending_writes_finished", "SET CONSTRAINTS ALL IMMEDIATE", "commit"]
        if bounded
        else ["business_writes", "commit"]
    )
