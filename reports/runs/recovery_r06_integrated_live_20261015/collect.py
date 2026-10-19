"""Observe actual default beat sources and PG facts; failures stay visible and no model is called."""

import hashlib
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text

from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.settings import load_application_settings

RUN = Path(__file__).resolve().parent
OUTSIDE = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/originals")
SHA = "1156b2ed6616e3a4297215c2893d2cbe633f5215"
ORIGIN = "http://127.0.0.1:25175"
ACTIVE = {"queued", "running", "retry_wait", "waiting_approval"}


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def write(name, content):
    (RUN / name).write_text(json.dumps(content, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def source_jobs(connection):
    rows = connection.execute(text("select j.job_id,j.status,j.idempotency_key,j.attempt_count,j.created_at,j.started_at,j.finished_at,j.error_code,j.result_ref,jp.payload from job_runs j join job_payloads jp on jp.job_id=j.job_id where j.job_type='collect_public_source_page' order by j.created_at,j.job_id")).mappings()
    jobs = []
    for row in rows:
        value = dict(row)
        payload = value.pop("payload")
        value["request"] = json.loads(bytes(payload))
        jobs.append(value)
    return jobs


def main():
    assert not (RUN / "collection_receipt.json").exists()
    started = now()
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    observations = []
    rest_requests = 0
    wait_reason = "observation_deadline"
    exception_type = None
    api_checks = []
    representative = {}
    page_count = 0
    jobs = []
    try:
        with httpx.Client(base_url="http://127.0.0.1:28012", timeout=10, trust_env=False) as client:
            ready = None
            for _ in range(30):
                rest_requests += 1
                try:
                    ready = client.get("/v1/health/ready")
                    if ready.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(2)
            else:
                raise RuntimeError("dependency_readiness_not_confirmed")
            write("ready.json", {"observed_at": now(), "http_status": ready.status_code, "body": ready.json()})
            deadline = time.monotonic() + 700
            complete_at = None
            while time.monotonic() < deadline:
                with engine.connect() as connection:
                    jobs = source_jobs(connection)
                roots = [job for job in jobs if (job["idempotency_key"] or "").startswith("source-poll-v1:")]
                states = Counter(job["status"] for job in jobs)
                observation = {"observed_at": now(), "source_jobs": len(jobs), "root_jobs": len(roots), "states": dict(states), "attempts": sum(job["attempt_count"] for job in jobs)}
                observations.append(observation)
                write("collection_observation.json", {"code_sha": SHA, "started_at": started, "latest": observation, "scope": "read-only source job observations; actual default beat creates roots"})
                if (RUN / "runtime_end.json").exists():
                    wait_reason = "runtime_stopped"
                    break
                if len({job["request"]["source_kind"] for job in roots}) == 9 and not any(job["status"] in ACTIVE for job in jobs):
                    if complete_at is None:
                        complete_at = time.monotonic()
                    if time.monotonic() - complete_at >= 65:
                        wait_reason = "all_source_jobs_terminal_plus_one_original_beat_interval"
                        break
                else:
                    complete_at = None
                time.sleep(5)
            response = client.post("/v1/auth/login", json={"username": os.environ["DIANZI_E2E_USERNAME"] + "-r06-integrated-admin", "password": os.environ["DIANZI_E2E_PASSWORD"]}, headers={"Origin": ORIGIN})
            rest_requests += 1
            assert response.status_code == 200
            csrf = response.json()["csrf_token"]
            cursor = None
            summaries = []
            while page_count < 10:
                query = {"limit": 100}
                if cursor is not None:
                    query["cursor"] = cursor
                result = client.get("/v1/documents", params=query)
                rest_requests += 1
                assert result.status_code == 200 and result.json()["data_mode"] == "live"
                page = result.json()
                summaries.extend(page["items"])
                page_count += 1
                cursor = page["next_cursor"]
                if cursor is None:
                    break
            assert len({item["document_id"] for item in summaries}) == len(summaries)
            source_by_id = {source.source_id: key for key, source in CATALOG_SOURCES.items()}
            for summary in summaries:
                kind = source_by_id[summary["source_id"]]
                if kind not in representative:
                    detail = client.get("/v1/documents/" + summary["document_id"], params={"evidence_limit": 100})
                    history = client.get("/v1/documents/" + summary["document_id"] + "/revisions")
                    rest_requests += 2
                    assert detail.status_code == 200 and history.status_code == 200
                    body = detail.json()
                    evidence = body["evidence"]
                    verified = all(hashlib.sha256(span["quote_text"].encode()).hexdigest() == span["quote_sha256"] for span in evidence)
                    assert verified and evidence and body["data_mode"] == "live"
                    public_sample = [{key: value for key, value in span.items() if key != "quote_text"} for span in evidence[:3]]
                    representative[kind] = {"document": summary, "evidence_total": body["evidence_total"], "evidence_samples": public_sample, "evidence_quotes_verified_in_memory": verified, "history": history.json(), "source_notes": body["source_notes"], "license_identifier": body["license_identifier"], "license_uri": body["license_uri"]}
            for job in [job for job in jobs if (job["idempotency_key"] or "").startswith("source-poll-v1:")]:
                result = client.get("/v1/jobs/" + job["job_id"])
                rest_requests += 1
                api_checks.append({"job_id": job["job_id"], "source_kind": job["request"]["source_kind"], "http_status": result.status_code, "state": result.json().get("status")})
            result = client.post("/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
            rest_requests += 1
            assert result.status_code in {200, 204}
            result = client.get("/v1/documents")
            rest_requests += 1
            assert result.status_code == 401
            response = client.post("/v1/auth/login", json={"username": os.environ["DIANZI_E2E_USERNAME"] + "-r06-integrated-viewer", "password": os.environ["DIANZI_E2E_PASSWORD"]}, headers={"Origin": ORIGIN})
            rest_requests += 1
            assert response.status_code == 200
            viewer_csrf = response.json()["csrf_token"]
            result = client.get("/v1/jobs/" + jobs[0]["job_id"])
            rest_requests += 1
            api_checks.append({"role": "viewer", "operation": "source_job_get", "http_status": result.status_code})
            assert result.status_code == 403
            result = client.post("/v1/sources/nvd_ollama/collect", json={"window_end": datetime.now(UTC).isoformat(), "stream_kind": "backfill", "max_pages": 1}, headers={"Origin": ORIGIN, "X-CSRF-Token": viewer_csrf, "Idempotency-Key": "r06-integrated-denied-viewer"})
            rest_requests += 1
            api_checks.append({"role": "viewer", "operation": "source_collect_post", "http_status": result.status_code})
            assert result.status_code == 403
            assert rest_requests <= 96
            client.post("/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": viewer_csrf})
            rest_requests += 1
    except Exception as error:
        exception_type = type(error).__name__
        wait_reason = "observation_or_api_failure"
    finally:
        with engine.connect() as connection:
            jobs = source_jobs(connection)
            counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("sources", "events", "documents", "document_revisions", "evidence", "job_runs", "fetch_attempts", "source_page_receipts", "content_objects")}
            attempts = [dict(row) for row in connection.execute(text("select source_id,attempted_at,outcome,http_status,response_content_hash,final_url from fetch_attempts order by attempted_at")).mappings()]
            cursors = [dict(row) for row in connection.execute(text("select * from source_cursors order by source_id,stream_kind")).mappings()]
            page_receipts = [dict(row) for row in connection.execute(text("select * from source_page_receipts order by committed_at")).mappings()]
            category_counts = [dict(row) for row in connection.execute(text("select s.source_id,s.category,count(distinct d.document_id) documents,count(distinct r.revision_id) revisions,count(distinct e.evidence_id) evidence from sources s left join documents d on d.source_id=s.source_id left join document_revisions r on r.document_id=d.document_id left join evidence e on e.revision_id=r.revision_id group by s.source_id,s.category order by s.source_id")).mappings()]
            revision_metadata = [dict(row) for row in connection.execute(text("select r.document_id,r.revision_id,r.source_response_hash,r.content_hash,r.source_published_at,r.source_modified_at,r.source_metadata,r.parse_status from document_revisions r order by r.revision_id")).mappings()]
            content = [dict(row) for row in connection.execute(text("select content_hash,size_bytes from content_objects order by content_hash")).mappings()]
            timing = dict(connection.execute(text("select count(*) revisions,count(*) filter(where source_published_at is null) missing_precise_publication,count(*) filter(where source_published_at>first_observed_at) future_publication,count(*) filter(where first_observed_at-source_published_at>interval '6 hours') over_six_hours,extract(epoch from percentile_cont(0.5) within group(order by first_observed_at-source_published_at) filter(where source_published_at is not null)) p50_seconds,extract(epoch from percentile_cont(0.95) within group(order by first_observed_at-source_published_at) filter(where source_published_at is not null)) p95_seconds,extract(epoch from max(first_observed_at-source_published_at) filter(where source_published_at is not null)) max_seconds from document_revisions")).mappings().one())
            runtime_observations = [dict(row) for row in connection.execute(text("select * from runtime_observations order by component")).mappings()]
        engine.dispose()
        roots = [job for job in jobs if (job["idempotency_key"] or "").startswith("source-poll-v1:")]
        source_status = {}
        for key, source in CATALOG_SOURCES.items():
            matching = [job for job in jobs if job["request"]["source_kind"] == key]
            source_status[key] = {"category": source.category.value, "root_jobs": [job["job_id"] for job in roots if job["request"]["source_kind"] == key], "job_status_counts": dict(Counter(job["status"] for job in matching)), "attempt_count": sum(job["attempt_count"] for job in matching), "http_attempts": [attempt for attempt in attempts if attempt["source_id"] == source.source_id], "persisted": next((row for row in category_counts if row["source_id"] == source.source_id), None)}
        receipt = {"started_at": started, "ended_at": now(), "code_sha": SHA, "data_mode": "live", "reason": wait_reason, "exception_type": exception_type, "observations": observations, "source_status": source_status, "jobs": jobs, "counts": counts, "cursors": cursors, "page_receipts": page_receipts, "representative_documents": representative, "api_checks": api_checks, "document_list_pages": page_count, "local_rest_requests": rest_requests, "root_creation": "actual original 60-second beat; no collect POST from this observer except viewer denial", "content_store": "MinIO", "model_calls": 0, "new_paid_api_cost": 0, "timing": timing, "timing_scope": "first discovery of historical/current catalog, not formal timely or missing-rate denominator", "runtime_observations": runtime_observations, "complete_r06_or_stage_accepted": False}
        write("collection_receipt.json", receipt)
        write("revision_metadata.json", {"code_sha": SHA, "revisions": revision_metadata})
        settings = load_application_settings()
        store = build_content_storage(settings)
        OUTSIDE.mkdir(parents=True, exist_ok=True)
        verified_objects = []
        total_bytes = 0
        for item in content:
            total_bytes += item["size_bytes"]
            assert len(verified_objects) < 1000 and total_bytes <= 80 * 1024**2
            body = store.read_verified(item["content_hash"])
            assert len(body) == item["size_bytes"] and hashlib.sha256(body).hexdigest() == item["content_hash"]
            target = OUTSIDE / (item["content_hash"] + ".body")
            if target.exists():
                assert target.read_bytes() == body
            else:
                target.write_bytes(body)
            verified_objects.append({**item, "hash_verified": True, "exported_outside_git": str(target)})
        write("object_verification.json", {"observed_at": now(), "store": "actual configured MinIO", "count": len(verified_objects), "total_bytes": total_bytes, "objects": verified_objects, "license_scope": "original and normalized bodies outside Git; only metadata retained here"})
        print(json.dumps({"collection_observation_complete": True, "exception_type": exception_type, "roots": len(roots), "counts": counts, "source_states": {key: value["job_status_counts"] for key, value in source_status.items()}, "model_calls": 0}))
    if exception_type:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
