"""明确限流响应头超出stdlib解析上限仍应安全阻塞；独立PG回归红例。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from test_reviewer_probes import (
    NOW, SOURCE_JOB_TYPE, ContentStore, build_source_page_handler, execute_job,
    install_wire, raw_response, queue, job_engine, empty_schema_engine,
    isolated_test_database_url, job_runs,
)


def test_raw_oversized_rate_header_does_not_become_seven_second_network_retry(
    monkeypatch, job_engine, tmp_path
):
    sockets = install_wire(
        monkeypatch, raw_response(429, b"Retry-After: " + b"9" * 65536 + b"\r\n")
    )
    job_id = queue(job_engine)
    handler = build_source_page_handler(ContentStore(tmp_path), clock=lambda: NOW)
    outcome = execute_job(job_engine, job_id, "parser-limit-review", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW)
    with Session(job_engine) as session:
        row = session.execute(select(job_runs)).mappings().one()
        actual = {"outcome": outcome, "error_code": row["error_code"],
                  "next_retry_at": row["next_retry_at"].isoformat() if row["next_retry_at"] else None}
    assert sockets[0].closed
    assert outcome == "blocked", actual
