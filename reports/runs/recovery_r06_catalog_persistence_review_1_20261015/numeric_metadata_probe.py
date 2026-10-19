"""Check replay after JSONB normalizes scientific number notation."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.orm import Session

import test_review_pg_probes as probes
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import document_revisions

failures = 0
for value in (1e20, 1e16, -0.0):
    fixture = probes.engine.__wrapped__()
    engine = next(fixture)
    with TemporaryDirectory(prefix="dianzi-number-probe-") as directory:
        store = ContentStore(Path(directory) / "raw")
        item = replace(probes.member(), metadata={"upstream_number": value})
        with Session(engine) as session, session.begin():
            first = probes.persist(session, store, (item,))
        with Session(engine) as session, session.begin():
            second = probes.persist(session, store, (item,))
            current = session.scalar(select(document_revisions.c.source_metadata).where(document_revisions.c.is_current.is_(True)))
        passed = second.new_revision_count == 0 and first.revision_ids == second.revision_ids
        failures += int(not passed)
        print(json.dumps({"input": value, "roundtrip_value": current["upstream_number"], "roundtrip_type": type(current["upstream_number"]).__name__, "second_new_revision_count": second.new_revision_count, "outcome": "passed" if passed else "failed"}), flush=True)
        try:
            next(fixture)
        except StopIteration:
            pass
sys.exit(1 if failures else 0)
