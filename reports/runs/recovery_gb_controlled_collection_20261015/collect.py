"""Submit finite authenticated public-source rounds and retain PG observations."""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text

RUN = Path(__file__).resolve().parent
CODE_SHA = "1927eeb00a7e0c1335f76340b0382f46102f08f2"
SOURCES = ("nvd_ollama", "vllm_vendor")
ROUND_SECONDS = 1800
MAXIMUM_ROUNDS = 12
MAXIMUM_SECONDS = 21600
MAXIMUM_REST_CALLS = 500
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def write(name, value):
    path = RUN / name
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def snapshot(engine, started):
    with engine.connect() as connection:
        jobs = [dict(row) for row in connection.execute(text("select job_id,status,attempt_count,error_code,result_ref,created_at,started_at,finished_at,next_retry_at from job_runs where job_type='collect_public_source_page' and created_at>=:started order by created_at,job_id limit 481"), {"started": started}).mappings()]
        cursors = [dict(row) for row in connection.execute(text("select source_id,stream_kind,cursor_json,last_successful_page,window_end,watermark_published_at,generation,updated_at from source_cursors where stream_kind='live' order by source_id")).mappings()]
        fetches = [dict(row) for row in connection.execute(text("select attempt_id,source_id,attempted_at,outcome,http_status,new_event_count,response_content_hash from fetch_attempts where attempted_at>=:started order by attempted_at limit 1441"), {"started": started}).mappings()]
        source_summary = [dict(row) for row in connection.execute(text("select s.source_id,s.name,s.category,count(f.attempt_id) as fetch_count,max(f.attempted_at) filter (where f.outcome='succeeded') as last_success_at,max(f.attempted_at) filter (where f.outcome<>'succeeded') as last_non_success_at from sources s left join fetch_attempts f on f.source_id=s.source_id and f.attempted_at>=:started group by s.source_id,s.name,s.category order by s.source_id"), {"started": started}).mappings()]
        receipts = [dict(row) for row in connection.execute(text("select source_id,stream_kind,page_key,entry_count,committed_at,request_sha256 from source_page_receipts where committed_at>=:started order by committed_at limit 481"), {"started": started}).mappings()]
        publication = [dict(row) for row in connection.execute(text("select d.source_id,count(*) as stored_revision_count,count(*) filter (where r.source_published_at is null) as missing_publication_count,count(*) filter (where r.source_published_at>r.first_observed_at) as future_publication_count,count(*) filter (where r.first_observed_at is null or r.ingested_at is null) as missing_observation_or_ingestion_count,count(*) filter (where r.ingested_at-r.source_published_at>interval '6 hours') as stored_revisions_older_than_six_hours_at_ingestion from documents d join document_revisions r on r.document_id=d.document_id group by d.source_id order by d.source_id")).mappings()]
        counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("events", "documents", "document_revisions", "evidence", "fetch_attempts", "source_page_receipts")}
    return {"observed_at": now(), "jobs": jobs, "cursors": cursors, "fetches": fetches, "source_summary": source_summary, "page_receipts": receipts, "publication_time_quality": publication, "counts": counts, "publication_statistics_scope": "All stored revisions include historical ingestion; no independent reference set, missed-item denominator or formal timeliness pass is claimed.", "empty_result_means_safe": False}


def main():
    started = datetime.fromisoformat(os.environ["DIANZI_COLLECTION_STARTED_AT"])
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    start_monotonic = time.monotonic()
    deadline = start_monotonic + MAXIMUM_SECONDS
    rest_calls = 0
    rounds = 0
    submissions = []
    reason = "bounded_deadline"
    write("collection_start.json", {"started_at": now(), "code_sha": CODE_SHA, "source_kinds": SOURCES, "maximum_rounds": MAXIMUM_ROUNDS, "round_interval_seconds": ROUND_SECONDS, "maximum_seconds": MAXIMUM_SECONDS, "max_pages_per_source_round": 20, "maximum_rest_calls": MAXIMUM_REST_CALLS, "product_model_calls": 0, "measurement_provider_calls": 0, "paid_api_calls": 0, "public_get_requires_gateway": True, "continuous_t54_pass_claim": False})
    with httpx.Client(base_url="http://127.0.0.1:28010", trust_env=False, timeout=10) as client:
        def request(method, path, **kwargs):
            nonlocal rest_calls
            if rest_calls >= MAXIMUM_REST_CALLS:
                raise RuntimeError("local REST call budget reached")
            rest_calls += 1
            return client.request(method, path, **kwargs)

        ready = None
        for attempt in range(60):
            try:
                ready = request("GET", "/v1/health/ready")
                if ready.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if (RUN / "collector_stop.request").exists():
                raise RuntimeError("startup stopped")
            time.sleep(1)
        write("ready_before_collection.json", {"observed_at": now(), "http_status": ready.status_code if ready is not None else None, "body": ready.json() if ready is not None else None, "startup_attempts": attempt + 1})
        assert ready is not None and ready.status_code == 200
        next_round = start_monotonic
        next_snapshot = 0
        with (RUN / "collection_observations.jsonl").open("x", encoding="utf-8") as observations:
            while time.monotonic() < deadline:
                if (RUN / "collector_stop.request").exists():
                    reason = "owned_supervisor_stop"
                    break
                if rounds < MAXIMUM_ROUNDS and time.monotonic() >= next_round:
                    login = request("POST", "/v1/auth/login", json={"username": os.environ["DIANZI_E2E_USERNAME"] + "-r04-admin", "password": os.environ["DIANZI_E2E_PASSWORD"]}, headers={"origin": "http://127.0.0.1:25300"})
                    assert login.status_code == 200, "authorized administrator login failed"
                    csrf_response = request("GET", "/v1/auth/csrf")
                    assert csrf_response.status_code == 200
                    csrf = csrf_response.json()["csrf_token"]
                    window_end = datetime.now(UTC).isoformat(timespec="seconds")
                    for source_kind in SOURCES:
                        response = request("POST", "/v1/sources/" + source_kind + "/collect", json={"window_end": window_end, "max_pages": 20, "stream_kind": "live"}, headers={"origin": "http://127.0.0.1:25300", "x-csrf-token": csrf, "idempotency-key": "gb-1927-20261015-round-" + str(rounds + 1) + "-" + source_kind})
                        item = {"round": rounds + 1, "source_kind": source_kind, "submitted_at": now(), "window_end": window_end, "http_status": response.status_code, "response": response.json()}
                        submissions.append(item)
                        write("submissions.json", submissions)
                        assert response.status_code == 202, "durable source submission failed"
                        status_response = request("GET", "/v1/jobs/" + response.json()["job_id"])
                        assert status_response.status_code == 200
                    rounds += 1
                    next_round = start_monotonic + rounds * ROUND_SECONDS
                if time.monotonic() >= next_snapshot:
                    observation = snapshot(engine, started)
                    observations.write(json.dumps(observation, ensure_ascii=False, default=str) + "\n")
                    observations.flush()
                    assert observations.tell() <= 16 * 1024**2, "observation log limit"
                    write("collection_latest.json", {"code_sha": CODE_SHA, "completed_submission_rounds": rounds, "local_rest_calls": rest_calls, **observation})
                    if observation["fetches"] and not (RUN / "first_source_observation.json").exists():
                        write("first_source_observation.json", {"code_sha": CODE_SHA, **observation})
                    next_snapshot = time.monotonic() + 30
                time.sleep(1)
    final = snapshot(engine, started)
    write("collection_end.json", {"started_at": started, "ended_at": now(), "code_sha": CODE_SHA, "reason": reason, "completed_submission_rounds": rounds, "local_rest_calls": rest_calls, "final_observation": final, "formal_pass": False})
    engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write("collection_failure.json", {"observed_at": now(), "error_type": type(error).__name__, "details": "withheld; see PG and HTTP receipts", "formal_pass": False})
        raise SystemExit(1) from None
