"""新候选头数量、普通断连、坏状态行、body截断的实际PG失败分类。"""

import traceback
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from test_reviewer_probes import (
    NOW, SOURCE_JOB_TYPE, ContentStore, build_source_page_handler, execute_job,
    install_wire, raw_response, queue, job_engine, empty_schema_engine,
    isolated_test_database_url, job_runs, source_page_receipts,
)
from ai_intel.infrastructure.network import NetworkPolicy, NetworkRequestError, create_network_gateway


@pytest.mark.parametrize("case,raw,outcome,error_code,delay", [
    ("excessive-headers", raw_response(429, b"X-Fill: synthetic\r\n" * 101 + b"Retry-After: 9000\r\n"), "blocked", "source_network_policy_denied", None),
    ("peer-disconnect", b"", "retry_wait", "network_error", 7),
    ("bad-status-line", b"SYNTHETIC_INVALID_STATUS\r\n\r\n", "retry_wait", "network_error", 7),
    ("body-truncated", b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{"x":1}', "retry_wait", "network_error", 7),
])
def test_pg_parser_policy_keeps_nonheader_network_failures_retryable(
    monkeypatch, job_engine, tmp_path, case, raw, outcome, error_code, delay
):
    sockets = install_wire(monkeypatch, raw)
    job_id = queue(job_engine)
    handler = build_source_page_handler(ContentStore(tmp_path), clock=lambda: NOW)
    assert execute_job(job_engine, job_id, "independent-recheck", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW) == outcome
    with Session(job_engine) as session:
        row = session.execute(select(job_runs)).mappings().one()
        assert row["error_code"] == error_code
        assert row["next_retry_at"] == (NOW + __import__("datetime").timedelta(seconds=delay) if delay else None)
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 0
    assert len(sockets) == 1 and sockets[0].closed


def test_bad_status_traceback_does_not_echo_untrusted_wire(monkeypatch):
    secret_marker = "synthetic-private-traceback-marker-246810"
    sockets = install_wire(monkeypatch, (secret_marker + "\r\n\r\n").encode())
    try:
        create_network_gateway(NetworkPolicy(("api.github.com",))).fetch("https://api.github.com/")
    except NetworkRequestError as error:
        trace = "".join(traceback.format_exception(error))
        assert secret_marker not in trace
        assert str(error) == "HTTP response status unavailable"
    else:
        pytest.fail("bad status line must be a safe network error")
    assert sockets[0].closed
