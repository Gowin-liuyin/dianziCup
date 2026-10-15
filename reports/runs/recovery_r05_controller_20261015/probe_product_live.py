"""一条真实公开事件问答，最多两次供应商调用；重放仅复用PG结果。"""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text

run = Path(__file__).resolve().parent / "product_live_23c1878"
assert (run / "runtime_start.json").is_file() and not (run / "question_start.json").exists()
clock = ZoneInfo("Asia/Shanghai")
secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
redactions = sorted(set(secrets) | {value[index:index + 8] for value in secrets for index in range(max(0, len(value) - 7))}, key=len, reverse=True)


def now():
    return datetime.now(clock).isoformat(timespec="seconds")


def save(name, value):
    encoded = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    for secret in redactions:
        encoded = encoded.replace(secret, "[REDACTED]")
    (run / name).write_text(encoded, encoding="utf-8")


def main():
    started = now()
    since = datetime.now(UTC)
    key = "r05-23c1878-public-question-one-20261015"
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 5})
    assert engine.url.database == "test_dianzi_r04_pipeline_20261015"
    with httpx.Client(base_url="http://127.0.0.1:28000", trust_env=False, timeout=90) as client:
        live = client.get("/v1/health/live")
        assert live.status_code == 200
        login = client.post("/v1/auth/login", json={"username": os.environ["DIANZI_E2E_USERNAME"] + "-r04-admin", "password": os.environ["DIANZI_E2E_PASSWORD"]}, headers={"origin": "http://127.0.0.1:25300"})
        assert login.status_code == 200, "owned test login failed"
        csrf = client.get("/v1/auth/csrf").json()["csrf_token"]
        listing = client.get("/v1/events", params={"q": "vllm", "limit": 1})
        assert listing.status_code == 200 and listing.json()["items"]
        event_id = listing.json()["items"][0]["event_id"]
        detail = client.get("/v1/events/" + event_id)
        save("selected_public_event.json", {"observed_at": now(), "status": detail.status_code, "body": detail.json()})
        payload = {"question": "这条公告明确说明了什么风险？只陈述一条能直接引用原文的事实；未给出的信息不要推测。", "mode": "library", "event_ids": [event_id]}
        save("question_start.json", {"started_at": started, "submitted_at": now(), "code_sha": "23c18784d71f1ed788072e6b3f2af70bac94fcb1", "request": payload, "maximum_supplier_calls": 2, "max_output_tokens": [4096, 2048], "client_timeout_seconds": 90, "fee": "unknown", "quality_evaluation": "not_run; no human gold"})
        timer = time.perf_counter()
        answer = client.post("/v1/questions", json=payload, headers={"origin": "http://127.0.0.1:25300", "x-csrf-token": csrf, "idempotency-key": key})
        elapsed = round((time.perf_counter() - timer) * 1000, 3)
        save("question_response.json", {"completed_at": now(), "status": answer.status_code, "complete_client_elapsed_milliseconds": elapsed, "body": answer.json()})
        if answer.status_code == 200:
            answer_id = answer.json()["answer_id"]
            historical = client.get("/v1/answers/" + answer_id)
            replay = client.post("/v1/questions", json=payload, headers={"origin": "http://127.0.0.1:25300", "x-csrf-token": csrf, "idempotency-key": key})
            save("answer_read_and_replay.json", {"observed_at": now(), "get_status": historical.status_code, "get_body": historical.json(), "replay_status": replay.status_code, "same_answer_id": replay.status_code == 200 and replay.json()["answer_id"] == answer_id, "replay_body": replay.json()})
        with engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(text("SELECT answer_id,response,model_trace,scope_epochs,created_at FROM grounded_answers WHERE created_at>=:since ORDER BY created_at"), {"since": since}).mappings()]
            chunks = connection.scalar(text("SELECT count(*) FROM retrieval_chunks"))
        save("pg_answer_trace.json", {"observed_at": now(), "rows": rows, "retrieval_chunk_count": chunks})
        actual_attempts = sum(len(row["model_trace"].get("attempts", [])) for row in rows)
        save("question_end.json", {"started_at": started, "ended_at": now(), "status": "passed" if answer.status_code == 200 else "failed", "http_status": answer.status_code, "complete_client_elapsed_milliseconds": elapsed, "actual_supplier_attempts": actual_attempts, "fee": "unknown", "code_sha": "23c18784d71f1ed788072e6b3f2af70bac94fcb1", "accuracy_or_sla_claim": False})
        print(json.dumps({"status": answer.status_code, "elapsed_milliseconds": elapsed, "supplier_attempts": actual_attempts, "fee": "unknown"}))
        assert answer.status_code == 200, "actual product question did not complete"
    engine.dispose()


if __name__ == "__main__":
    main()
