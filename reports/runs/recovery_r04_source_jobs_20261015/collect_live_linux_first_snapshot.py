"""认证提交两固定公源，观察真实 PG/队列并读取实际证据，不注入 fixture。"""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text

RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r04_source_jobs_20261015/live_segment_1")
CONFIG = Path("/tmp/dianzi-r04-live-20261015/private/runtime.json")
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def write(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    assert not (RUN / "collection_start.json").exists(), "collection segment already used"
    configuration = json.loads(CONFIG.read_text())
    environment = configuration["environment"]
    engine = create_engine(environment["DATABASE_URL"], connect_args={"connect_timeout": 3})
    started = now()
    window = datetime.now(UTC).isoformat()
    submitted = []
    with httpx.Client(base_url="http://127.0.0.1:28000", trust_env=False, timeout=10) as client:
        ready = client.get("/v1/health/ready")
        write("ready_before_collection.json", {"observed_at": now(), "status": ready.status_code, "body": ready.json()})
        assert ready.status_code == 200, "fixed runtime must be ready before source collection"
        login = client.post("/v1/auth/login", json={"username": environment["DIANZI_E2E_USERNAME"] + "-r04-admin", "password": environment["DIANZI_E2E_PASSWORD"]}, headers={"origin": "http://127.0.0.1:25300"})
        assert login.status_code == 200, "source administrator login failed"
        csrf = client.get("/v1/auth/csrf").json()["csrf_token"]
        for kind in ("nvd_ollama", "vllm_vendor"):
            response = client.post("/v1/sources/" + kind + "/collect",
                json={"window_end": window, "max_pages": 20, "stream_kind": "backfill"},
                headers={"origin": "http://127.0.0.1:25300", "x-csrf-token": csrf, "idempotency-key": "r04-real-20261015-" + kind})
            submitted.append({"source_kind": kind, "submitted_at": now(), "http_status": response.status_code, "response": response.json()})
            assert response.status_code == 202, "source page was not durably queued"
        write("collection_start.json", {"started_at": started, "code_sha": configuration["code_sha"], "submitted": submitted,
            "source_mode": "actual public gateway GET", "maximum_observation_seconds": 180,
            "continuous_monitoring_claim": False, "source_time_watermark_claim": False})
        deadline = time.monotonic() + 180
        reason = "observation_deadline"
        with (RUN / "collection_observations.jsonl").open("x", encoding="utf-8") as observations:
            while time.monotonic() < deadline:
                with engine.connect() as connection:
                    jobs = [dict(row) for row in connection.execute(text("SELECT job_id,status,attempt_count,error_code,result_ref FROM job_runs WHERE job_type='collect_public_source_page' ORDER BY created_at,job_id LIMIT 100")).mappings()]
                    cursors = [dict(row) for row in connection.execute(text("SELECT source_id,stream_kind,cursor_json,last_successful_page FROM source_cursors ORDER BY source_id")).mappings()]
                    counts = {name: connection.scalar(text("SELECT count(*) FROM " + name)) for name in ("events", "documents", "document_revisions", "evidence", "fetch_attempts", "source_page_receipts")}
                observation = {"observed_at": now(), "jobs": jobs, "cursors": cursors, "counts": counts}
                observations.write(json.dumps(observation) + "\n")
                observations.flush()
                if len(cursors) == 2 and all(row["cursor_json"].get("window_complete") is True for row in cursors):
                    reason = "both_pagination_sweeps_complete"
                    break
                if any(row["status"] in {"failed", "blocked", "partial"} for row in jobs):
                    reason = "page_failed_blocked_or_partial"
                    break
                time.sleep(2)
        write("collection_end.json", {"started_at": started, "ended_at": now(), "code_sha": configuration["code_sha"], "reason": reason, "final_observation": observation,
            "continuous_monitoring_claim": False, "source_time_watermark_claim": False,
            "fee": "unknown; anonymous public source GET, product model calls 0"})
        listing = client.get("/v1/events", params={"limit": 20})
        write("actual_event_list.json", {"observed_at": now(), "status": listing.status_code, "body": listing.json()})
        assert listing.status_code == 200
        if listing.json()["items"]:
            target = listing.json()["items"][0]["event_id"]
            detail = client.get("/v1/events/" + target)
            write("actual_event_detail.json", {"observed_at": now(), "status": detail.status_code, "body": detail.json()})
            assert detail.status_code == 200
            evidence_ids = [item for claim in detail.json()["claims"] for item in claim["evidence_ids"]]
            if evidence_ids:
                response = client.get("/v1/evidence/" + evidence_ids[0])
                write("actual_evidence.json", {"observed_at": now(), "status": response.status_code, "body": response.json()})
                assert response.status_code == 200
                assert hashlib.sha256(response.json()["quote_text"].encode()).hexdigest() == response.json()["quote_sha256"]
        print(json.dumps({"started_at": started, "ended_at": now(), "reason": reason, "counts": counts}))
    engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write("collection_failed.json", {"observed_at": now(), "error_type": type(error).__name__, "details": "withheld; inspect non-secret HTTP and PG observations"})
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        raise SystemExit(1) from None
