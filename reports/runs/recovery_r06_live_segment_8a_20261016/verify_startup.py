"""Check actual beat-created work, API authentication, original bytes and PG evidence."""

from common import DATABASE, OBSERVER, PRODUCT_SHA, RUN, RUN_ID, now, verify_authorization, write

verify_authorization()

import hashlib
import json
import os
import time
from collections import Counter

import httpx
from sqlalchemy import create_engine, text
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.settings import load_application_settings

engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
started = now()
write("startup_validation_start.json", {"started_at": started, "product_sha": PRODUCT_SHA, "read_only_pg": True, "source_submit_requests": 0, "maximum_seconds": 600})
deadline = time.monotonic() + 600
with httpx.Client(base_url="http://127.0.0.1:28013", timeout=10, trust_env=False) as client:
    while time.monotonic() < deadline:
        if (RUN / "runtime_end.json").exists():
            raise RuntimeError("owned segment stopped before startup validation")
        try:
            ready = client.get("/v1/health/ready")
            if ready.status_code == 200:
                break
        except httpx.TransportError:
            pass
        time.sleep(2)
    else:
        raise RuntimeError("API readiness not observed")
    write("ready.json", {"observed_at": now(), "http_status": ready.status_code, "body": ready.json()})
    minio = client.get("http://127.0.0.1:29400/minio/health/live")
    assert minio.status_code == 200
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            assert connection.scalar(text("select current_database()")) == DATABASE
            jobs = []
            for row in connection.execute(text("select j.job_id,j.status,j.attempt_count,j.error_code,j.idempotency_key,p.payload from job_runs j join job_payloads p on p.job_id=j.job_id where j.job_type='collect_public_source_page' order by j.created_at,j.job_id")).mappings():
                payload = json.loads(bytes(row["payload"]))
                jobs.append({key: row[key] for key in ("job_id", "status", "attempt_count", "error_code", "idempotency_key")} | {"source_kind": payload["source_kind"]})
            receipt_kinds = set(connection.execute(text("select distinct source_kind from source_response_receipts")).scalars())
            runtime = [dict(row) for row in connection.execute(text("select * from runtime_observations order by component")).mappings()]
        roots = [job for job in jobs if (job["idempotency_key"] or "").startswith("source-poll-v1:")]
        write("startup_validation_progress.json", {"observed_at": now(), "root_sources": sorted({job["source_kind"] for job in roots}), "response_receipt_sources": sorted(receipt_kinds), "jobs": len(jobs), "states": dict(Counter(job["status"] for job in jobs))})
        if set(CATALOG_SOURCES) == {job["source_kind"] for job in roots} == receipt_kinds and all(job["attempt_count"] > 0 for job in roots):
            break
        if (RUN / "runtime_end.json").exists():
            raise RuntimeError("owned runtime ended before nine source receipts")
        time.sleep(5)
    else:
        raise RuntimeError("nine beat roots and response receipts not observed within bound")
    response = client.post("/v1/auth/login", json={"username": os.environ["DIANZI_E2E_USERNAME"] + "-r06-live-8a-admin", "password": os.environ["DIANZI_E2E_PASSWORD"]}, headers={"Origin": "http://127.0.0.1:25176"})
    assert response.status_code == 200
    csrf = response.json()["csrf_token"]
    checks = []
    for path in ("/v1/sources", "/v1/documents", "/v1/jobs/" + roots[0]["job_id"]):
        result = client.get(path)
        checks.append({"path": path, "status": result.status_code})
        assert result.status_code == 200
    result = client.post("/v1/auth/logout", headers={"Origin": "http://127.0.0.1:25176", "X-CSRF-Token": csrf})
    assert result.status_code in {200, 204}
    denied = client.get("/v1/documents")
    assert denied.status_code == 401

with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection, connection.begin():
    connection.execute(text("SET TRANSACTION READ ONLY"))
    counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("sources", "documents", "document_revisions", "evidence", "source_response_receipts", "source_page_receipts", "content_objects", "fetch_attempts")}
    receipts = [dict(row) for row in connection.execute(text("select receipt_id,job_id,source_kind,source_id,attempt_count,response_ordinal,observed_at,http_status,response_content_hash,response_size_bytes,parse_outcome,error_code,input_cursor_sha256 from source_response_receipts order by observed_at,receipt_id")).mappings()]
    content = [dict(row) for row in connection.execute(text("select content_hash,size_bytes from content_objects order by content_hash")).mappings()]
    spans = list(connection.execute(text("select e.evidence_id,e.quote,e.quote_sha256,e.start_offset,e.end_offset,e.coordinate_version,e.supports_claim,b.block_text,b.start_offset block_start,b.page_number,b.json_pointer from evidence e left join text_blocks b on b.block_id=e.block_id")).mappings())
    source_counts = [dict(row) for row in connection.execute(text("select s.source_id,s.category,count(distinct d.document_id) documents,count(distinct r.revision_id) revisions from sources s left join documents d on d.source_id=s.source_id left join document_revisions r on r.document_id=d.document_id group by s.source_id,s.category order by s.source_id")).mappings()]
    cursor_rows = list(connection.execute(text("select source_id,generation,cursor_json from source_cursors order by source_id")).mappings())
    timing = dict(connection.execute(text("select count(*) stored_revisions,count(*) filter(where source_published_at is null) publication_unknown,count(*) filter(where source_published_at>first_observed_at) future_publication,count(*) filter(where ingested_at-source_published_at>interval '6 hours') older_than_six_hours,extract(epoch from percentile_cont(0.5) within group(order by ingested_at-source_published_at) filter(where source_published_at is not null)) p50_seconds,extract(epoch from percentile_cont(0.95) within group(order by ingested_at-source_published_at) filter(where source_published_at is not null)) p95_seconds,extract(epoch from max(ingested_at-source_published_at) filter(where source_published_at is not null)) max_seconds from document_revisions")).mappings().one())
engine.dispose()
invalid = []
evidence_samples = []
for span in spans:
    relative = span["start_offset"] - span["block_start"] if span["block_start"] is not None else None
    valid = relative is not None and relative >= 0 and span["block_text"][relative:relative + span["end_offset"] - span["start_offset"]] == span["quote"] and hashlib.sha256(span["quote"].encode()).hexdigest() == span["quote_sha256"]
    if not valid:
        invalid.append(span["evidence_id"])
    if len(evidence_samples) < 9:
        evidence_samples.append({key: span[key] for key in ("evidence_id", "quote_sha256", "start_offset", "end_offset", "coordinate_version", "supports_claim", "page_number", "json_pointer")})
assert not invalid
store = build_content_storage(load_application_settings())
verified = []
total = 0
for item in content:
    total += item["size_bytes"]
    assert len(verified) < 1000 and total <= 80 * 1024**2
    body = store.read_verified(item["content_hash"])
    assert len(body) == item["size_bytes"] and hashlib.sha256(body).hexdigest() == item["content_hash"]
    verified.append({**item, "read_verified": True})
write("object_verification_startup.json", {"verified_at": now(), "store": "MinIO", "count": len(verified), "total_bytes": total, "objects": verified, "raw_bodies_only_outside_repository": True})
cursor_audit = []
for source_kind, source in CATALOG_SOURCES.items():
    cursor = next((row for row in cursor_rows if row["source_id"] == source.source_id), None)
    source_receipts = [row for row in receipts if row["source_kind"] == source_kind]
    failed_only = source_receipts and not any(row["parse_outcome"] == "normalized" for row in source_receipts)
    if failed_only:
        assert cursor is None or cursor["generation"] == 0
    cursor_audit.append({"source_kind": source_kind, "generation": cursor["generation"] if cursor else None, "failed_only": bool(failed_only), "no_forward_cursor_on_failed_only": cursor is None or cursor["generation"] == 0 if failed_only else None, "cursor_json_recorded": False})
assert {row["component"] for row in runtime} >= {"worker", "scheduler"}
observer_run = OBSERVER / ("live_" + RUN_ID)
assert (observer_run / "journal.jsonl").exists() or any(observer_run.glob("*.jsonl"))
write("startup_receipt.json", {"started_at": started, "verified_at": now(), "product_sha": PRODUCT_SHA, "observer_sha": "1c4cce9770bfa29d08728a0131f7fc7fe714f9bc", "database": DATABASE, "api_checks": checks, "logout_then_unauthenticated_status": denied.status_code, "minio_health_status": minio.status_code, "counts": counts, "root_jobs": roots, "source_root_creator": "original default beat only; no collect POST", "source_counts": source_counts, "source_response_receipts": receipts, "cursor_verification": cursor_audit, "evidence_checked": len(spans), "invalid_evidence": invalid, "evidence_samples": evidence_samples, "evidence_scope": "block coordinate and quote hash integrity; semantic support not asserted", "runtime_observations": runtime, "objects_verified": len(verified), "timing": timing, "timing_denominator": "all stored revisions including initial historical discovery; missing and future time counts separately retained", "independent_missed_item_reference": "not_run", "browser": "not_run", "data_mode": "live", "fixtures": 0, "model_requests": 0, "model_provider": "not_configured", "paid_source_cost": "unknown", "formal_six_hour_pass": False})
print(json.dumps({"startup_verified": True, "root_jobs": len(roots), "counts": counts, "evidence_checked": len(spans), "objects_verified": len(verified), "formal_six_hour_pass": False}))
