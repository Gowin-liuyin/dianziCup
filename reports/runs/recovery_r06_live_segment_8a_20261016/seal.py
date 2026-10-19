"""Freeze safe terminal observation bytes and independently audit this segment's outputs."""

from common import OBSERVER, OBSERVER_SHA, PRODUCT_SHA, ROOT, RUN, RUN_ID, now, verify_authorization, write

verify_authorization()

import hashlib
import json
import os
import shutil
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, str(OBSERVER))
from observation_log import replay

observer_run = OBSERVER / ("live_" + RUN_ID)
journal = observer_run / "collection_observations.jsonl"
state = replay(journal)
assert state.terminal_receipt_present
start = json.loads((RUN / "runtime_start.json").read_text())
end = json.loads((RUN / "runtime_end.json").read_text())
assert end["reason"] == "source_running_watchdog"
frozen = RUN / "observer_terminal_archive"
frozen.mkdir(exist_ok=True)
observations = {}
for path in observer_run.iterdir():
    if path.is_file():
        destination = frozen / path.name
        if destination.exists():
            assert destination.read_bytes() == path.read_bytes()
        else:
            shutil.copyfile(path, destination)
        observations[path.name] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
with engine.connect() as connection:
    connection.execute(text("SET TRANSACTION READ ONLY"))
    counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("documents", "document_revisions", "evidence", "content_objects", "source_response_receipts", "source_page_receipts", "fetch_attempts")}
    source_results = [dict(row) for row in connection.execute(text("select s.source_id,s.category,count(distinct d.document_id) documents,count(distinct r.revision_id) revisions from sources s left join documents d on d.source_id=s.source_id left join document_revisions r on r.document_id=d.document_id group by s.source_id,s.category order by s.source_id")).mappings()]
    spans = list(connection.execute(text("select e.evidence_id,e.quote,e.quote_sha256,e.start_offset,e.end_offset,b.block_text,b.start_offset block_start from evidence e left join text_blocks b on b.block_id=e.block_id")).mappings())
    timing = dict(connection.execute(text("select count(*) stored_revisions,count(*) filter(where source_published_at is null) publication_unknown,count(*) filter(where source_published_at>first_observed_at) future_publication,count(*) filter(where ingested_at-source_published_at>interval '6 hours') older_than_six_hours,extract(epoch from percentile_cont(0.5) within group(order by ingested_at-source_published_at) filter(where source_published_at is not null)) p50_seconds,extract(epoch from percentile_cont(0.95) within group(order by ingested_at-source_published_at) filter(where source_published_at is not null)) p95_seconds,extract(epoch from max(ingested_at-source_published_at) filter(where source_published_at is not null)) max_seconds from document_revisions")).mappings().one())
engine.dispose()
bad_spans = []
for span in spans:
    offset = span["start_offset"] - span["block_start"] if span["block_start"] is not None else None
    valid = offset is not None and offset >= 0 and span["block_text"][offset:offset + span["end_offset"] - span["start_offset"]] == span["quote"] and hashlib.sha256(span["quote"].encode()).hexdigest() == span["quote_sha256"]
    if not valid:
        bad_spans.append(span["evidence_id"])
assert not bad_spans
secret_values = [value.encode() for value in json.loads(os.environ["DIANZI_LOG_SECRET_VALUES"]) if value]
findings = []
scanned = 0
for path in RUN.rglob("*"):
    if not path.is_file():
        continue
    scanned += 1
    contents = path.read_bytes()
    if any(secret in contents for secret in secret_values):
        findings.append(str(path.relative_to(RUN)))
assert not findings
from datetime import datetime

seconds = (datetime.fromisoformat(end["ended_at"]) - datetime.fromisoformat(start["started_at"])).total_seconds()
write("terminal_seal_receipt.json", {"sealed_at": now(), "product_sha": PRODUCT_SHA, "observer_sha": OBSERVER_SHA, "observer_checkout_sha": "b08824f738ca185776916ae02689d8507f956c5c", "source_tree": str(ROOT), "observer_live_run": str(observer_run), "actual_started_at": start["started_at"], "actual_ended_at": end["ended_at"], "actual_wall_seconds": seconds, "observer_terminal_present": state.terminal_receipt_present, "observer_records": state.sequence, "observer_original_files": observations, "counts": counts, "source_results": source_results, "evidence_spans_checked": len(spans), "invalid_evidence_count": len(bad_spans), "timing": timing, "timing_scope": "all stored initial catalog revisions; no independent missing-item reference or timely pass", "secret_value_scan": {"files": scanned, "findings": findings}, "startup_validation": "failed", "browser": "not_run", "formal_six_hour_pass": False})
print(json.dumps({"actual_wall_seconds": seconds, "observer_terminal_verified": True, "counts": counts, "evidence_spans_checked": len(spans), "secret_findings": len(findings)}))
