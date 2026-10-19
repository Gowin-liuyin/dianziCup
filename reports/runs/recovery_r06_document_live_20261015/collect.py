"""Two actual source jobs via authenticated REST; bounded local polling and no model requests."""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text

RUN = Path(__file__).resolve().parent
ORIGIN = "http://127.0.0.1:25174"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    assert not (RUN / "collection_receipt.json").exists()
    started = now()
    requests = 0
    with httpx.Client(base_url="http://127.0.0.1:28011", timeout=10, trust_env=False) as client:
        for _ in range(30):
            requests += 1
            try:
                ready = client.get("/v1/health/ready")
                if ready.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("real dependencies did not become ready")
        (RUN / "ready.json").write_text(json.dumps({"observed_at": now(), "http_status": ready.status_code, "body": ready.json()}, indent=2) + "\n", encoding="utf-8")
        response = client.post("/v1/auth/login", json={"username": os.environ["DIANZI_E2E_USERNAME"] + "-r06-doc-admin", "password": os.environ["DIANZI_E2E_PASSWORD"]}, headers={"Origin": ORIGIN})
        requests += 1
        assert response.status_code == 200
        csrf = response.json()["csrf_token"]
        jobs = {}
        for source in ("nvd_ollama", "vllm_vendor"):
            result = client.post("/v1/sources/" + source + "/collect", json={"window_end": datetime.now(UTC).isoformat(), "stream_kind": "backfill", "max_pages": 1}, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf, "Idempotency-Key": "r06-doc-live-" + uuid4().hex})
            requests += 1
            assert result.status_code == 202
            jobs[source] = result.json()
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            pending = False
            for source, previous in tuple(jobs.items()):
                if previous["status"] in {"succeeded", "partial", "failed", "blocked"}:
                    continue
                result = client.get("/v1/jobs/" + previous["job_id"])
                requests += 1
                assert result.status_code == 200 and requests <= 96
                jobs[source] = result.json()
                if jobs[source]["status"] not in {"succeeded", "partial", "failed", "blocked"}:
                    pending = True
            if not pending:
                break
            time.sleep(3)
        assert all(job["status"] in {"partial", "succeeded"} for job in jobs.values())
        response = client.get("/v1/documents", params={"limit": 100})
        requests += 1
        assert response.status_code == 200 and response.json()["data_mode"] == "live"
        documents = response.json()["items"]
        assert documents and {item["source_category"] for item in documents} == {"structured_vulnerability", "vendor_advisory"}
        first = documents[0]
        detail = client.get("/v1/documents/" + first["document_id"])
        requests += 1
        assert detail.status_code == 200 and detail.json()["evidence_total"] > 0
        history = client.get("/v1/documents/" + first["document_id"] + "/revisions")
        requests += 1
        assert history.status_code == 200 and history.json()["items"][0]["revision_id"] == first["revision_id"]
        logout = client.post("/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        requests += 1
        assert logout.status_code in {200, 204}
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3})
    with engine.connect() as connection:
        counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("events", "documents", "document_revisions", "evidence", "job_runs", "fetch_attempts", "source_page_receipts")}
        attempts = [dict(row) for row in connection.execute(text("select source_id,http_status,response_content_hash from fetch_attempts order by attempted_at")).mappings()]
    engine.dispose()
    (RUN / "collection_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": now(), "code_sha": "0a45185ae3ffb73a6d186b98421e26a52f78bfc6", "data_mode": "live", "authentication": "actual PG session/CSRF; cookie not recorded", "jobs": jobs, "counts": counts, "attempts": attempts, "first_document": first, "first_detail": detail.json(), "first_history": history.json(), "local_rest_requests": requests, "local_rest_request_limit": 96, "source_job_page_limit_each": 1, "model_calls": 0, "scope": "two existing real sources through worker/PG/document GET; new seven sources and browser still separate"}, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "counts": counts, "jobs": {key: value["status"] for key, value in jobs.items()}, "model_calls": 0}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        (RUN / "collection_failure.json").write_text(json.dumps({"failed_at": now(), "error_type": type(error).__name__, "details": "withheld; product failure/raw commands retained"}, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(1) from None
