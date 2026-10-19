"""Read the stopped isolated DB, verify all final objects/evidence and preserve metadata only."""

import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.settings import load_application_settings
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES

RUN = Path(__file__).resolve().parent
OUTSIDE = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/originals")
SHA = "1156b2ed6616e3a4297215c2893d2cbe633f5215"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def write(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def main():
    assert (RUN / "runtime_end.json").exists()
    assert not (RUN / "final_receipt.json").exists()
    started = now()
    url = make_url(os.environ["DATABASE_URL"])
    assert url.database == "test_dianzi_r06_integrated_live_20261015" and url.host in {"localhost", "127.0.0.1"}
    engine = create_engine(url, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    with engine.connect() as connection:
        counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("sources", "events", "documents", "document_revisions", "evidence", "job_runs", "fetch_attempts", "source_page_receipts", "content_objects")}
        jobs = []
        for row in connection.execute(text("select j.job_id,j.status,j.error_code,j.attempt_count,j.created_at,j.finished_at,j.idempotency_key,p.payload from job_runs j join job_payloads p on p.job_id=j.job_id where j.job_type='collect_public_source_page' order by j.created_at")).mappings():
            value = dict(row)
            value["request"] = json.loads(bytes(value.pop("payload")))
            jobs.append(value)
        attempts = [dict(row) for row in connection.execute(text("select source_id,attempted_at,outcome,http_status,response_content_hash,final_url from fetch_attempts order by attempted_at")).mappings()]
        transitions = [dict(row) for row in connection.execute(text("select t.job_id,t.attempt_count,t.from_status,t.to_status,t.reason,t.changed_at from job_transitions t join job_runs j on j.job_id=t.job_id where j.job_type='collect_public_source_page' order by t.transition_sequence")).mappings()]
        revisions = [dict(row) for row in connection.execute(text("select d.source_id,r.document_id,r.revision_id,r.revision_number,r.is_current,r.content_hash,r.source_response_hash,r.source_published_at,r.source_modified_at,r.source_metadata,r.first_observed_at,r.ingested_at,r.parse_status from document_revisions r join documents d on d.document_id=r.document_id order by d.source_id,r.document_id,r.revision_number")).mappings()]
        contents = [dict(row) for row in connection.execute(text("select content_hash,size_bytes from content_objects order by content_hash")).mappings()]
        cursors = [dict(row) for row in connection.execute(text("select * from source_cursors order by source_id,stream_kind")).mappings()]
        page_receipts = [dict(row) for row in connection.execute(text("select * from source_page_receipts order by committed_at")).mappings()]
        evidence_rows = list(connection.execute(text("select e.evidence_id,e.quote,e.quote_sha256,e.start_offset,e.end_offset,e.supports_claim,e.coordinate_version,b.block_text,b.start_offset block_start,b.page_number,b.json_pointer from evidence e left join text_blocks b on b.block_id=e.block_id order by e.evidence_id")).mappings())
        timings = dict(connection.execute(text("select count(*) revisions,count(*) filter(where source_published_at is null) missing_precise_publication,count(*) filter(where source_published_at>first_observed_at) future_publication,count(*) filter(where first_observed_at-source_published_at>interval '6 hours') over_six_hours,extract(epoch from percentile_cont(0.5) within group(order by first_observed_at-source_published_at) filter(where source_published_at is not null)) p50_seconds,extract(epoch from percentile_cont(0.95) within group(order by first_observed_at-source_published_at) filter(where source_published_at is not null)) p95_seconds,extract(epoch from max(first_observed_at-source_published_at) filter(where source_published_at is not null)) max_seconds from document_revisions")).mappings().one())
    engine.dispose()
    baseline = create_engine(url.set(database="test_dianzi_r04_pipeline_20261015"), connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    with baseline.connect() as connection:
        baseline_schema = connection.scalar(text("select version_num from alembic_version"))
        assert baseline_schema == "0014_grounded_answer_vectors"
    baseline.dispose()
    source_results = {}
    for key, source in CATALOG_SOURCES.items():
        selected = [job for job in jobs if job["request"]["source_kind"] == key]
        saved = [revision for revision in revisions if revision["source_id"] == source.source_id]
        source_results[key] = {"source_id": source.source_id, "category": source.category.value, "job_count": len(selected), "job_states": dict(Counter(job["status"] for job in selected)), "job_attempts": sum(job["attempt_count"] for job in selected), "root_job_count": sum((job["idempotency_key"] or "").startswith("source-poll-v1:") for job in selected), "documents": len({revision["document_id"] for revision in saved}), "revisions": len(saved), "http_records": [attempt for attempt in attempts if attempt["source_id"] == source.source_id]}
    bad_spans = []
    for row in evidence_rows:
        relative = row["start_offset"] - row["block_start"] if row["block_start"] is not None else None
        valid = relative is not None and relative >= 0 and row["block_text"][relative:relative + row["end_offset"] - row["start_offset"]] == row["quote"]
        valid = valid and hashlib.sha256(row["quote"].encode()).hexdigest() == row["quote_sha256"]
        if not valid:
            bad_spans.append(row["evidence_id"])
    store = build_content_storage(load_application_settings())
    verified = []
    total_bytes = 0
    OUTSIDE.mkdir(parents=True, exist_ok=True)
    for item in contents:
        total_bytes += item["size_bytes"]
        assert len(verified) < 1000 and total_bytes <= 80 * 1024**2
        body = store.read_verified(item["content_hash"])
        assert len(body) == item["size_bytes"] and hashlib.sha256(body).hexdigest() == item["content_hash"]
        target = OUTSIDE / (item["content_hash"] + ".body")
        if target.exists():
            assert target.read_bytes() == body
        else:
            target.write_bytes(body)
        verified.append({**item, "read_back_hash_verified": True, "original_path_outside_git": str(target)})
    write("object_verification_final.json", {"verified_at": now(), "count": len(verified), "total_bytes": total_bytes, "objects": verified})
    write("source_jobs_final.json", {"code_sha": SHA, "jobs": jobs, "transitions": transitions})
    write("revision_metadata_final.json", {"code_sha": SHA, "revisions": revisions})
    write("final_receipt.json", {"started_at": started, "ended_at": now(), "code_sha": SHA, "counts": counts, "source_results": source_results, "cursors": cursors, "page_receipts": page_receipts, "source_job_count": len(jobs), "source_job_attempts": sum(job["attempt_count"] for job in jobs), "actual_saved_http_records": len(attempts), "diagnostic_fixed_source_requests": 4, "all_http_exchanges_cannot_be_inferred_from_pg_job_attempts": True, "evidence_checked": len(evidence_rows), "invalid_evidence_ids": bad_spans, "evidence_check_scope": "saved block text offsets/hash/supports_claim=false; no assertion of semantic support", "timing": timings, "timing_scope": "initial historic/current discovery, not independently complete reference denominator or six-hour target proof", "baseline_gb_schema_read_only": baseline_schema, "model_calls": 0, "new_paid_api_cost": 0, "actual_confirmed_categories": sorted({source["category"] for source in source_results.values() if source["documents"] > 0}), "r06_stage_complete": False})
    print(json.dumps({"counts": counts, "source_jobs": len(jobs), "source_job_attempts": sum(job["attempt_count"] for job in jobs), "saved_http_records": len(attempts), "all_evidence_checked": len(evidence_rows), "invalid_evidence_count": len(bad_spans), "objects_verified": len(verified)}))


if __name__ == "__main__":
    main()
