"""独立构造的原始HTTP与隔离PG负例；所有上游响应均明确为synthetic。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from email.utils import format_datetime
import io
import json
from pathlib import Path
import socket
import ssl
import sys
from threading import Event

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

WT = Path("C:/Users/yinha/.codex/worktrees/r04-rate-limits-independent-review-1/dianzi")
sys.path.insert(0, str(WT))
sys.path.insert(0, str(WT / "backend/tests"))
sys.path.insert(0, str(WT / "backend/tests/integration"))
from conftest import isolated_test_database_url as isolated_test_database_url
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from test_r04_source_jobs_pg import job_engine as job_engine, queue, nvd_response

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.http_transport import PinnedHttpTransport
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationFailure, GenerationRequest
from ai_intel.infrastructure.network import FetchResult, NetworkPolicy, NetworkPolicyViolation, NetworkRequestError, create_network_gateway
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, _http_failure, build_source_page_handler
from ai_intel.knowledge.models import document_revisions, job_runs, outbox_events, source_cursors, source_page_receipts
from ai_intel.workers.executor import JobExecutionError, execute_job

NOW = datetime(2026, 10, 15, 12, 34, 56, 900000, tzinfo=UTC)
SHORT_DATE = "Thu, 15 Oct 2026 12:35:05 GMT"
URL = "https://api.github.com/repos/vllm-project/vllm/security-advisories"


class ReviewSocket:
    def __init__(self, raw):
        self.raw = raw
        self.sent = []
        self.closed = False

    def connect(self, address):
        self.address = address

    def getpeername(self):
        return "93.184.216.34", 443

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, value):
        self.sent.append(value)

    def makefile(self, mode):
        return io.BytesIO(self.raw)

    def do_handshake(self):
        pass

    def shutdown(self, how):
        self.closed = True

    def close(self):
        self.closed = True


def raw_response(status, headers=b"", body=b""):
    return (f"HTTP/1.1 {status} Synthetic\r\nContent-Type: application/json\r\n".encode()
            + headers + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)


def install_wire(monkeypatch, raw):
    sockets = []
    def create_socket(*args):
        result = ReviewSocket(raw)
        sockets.append(result)
        return result
    monkeypatch.setattr(socket, "socket", create_socket)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", lambda self, sock, **kwargs: sock)
    return sockets


def classify(status, headers, now=NOW):
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(FetchResult(URL, status, "application/json", b"", headers), clock=lambda: now)
    return caught.value


@pytest.mark.parametrize("name", [b"Retry-After", b"X-RateLimit-Remaining", b"X-RateLimit-Reset"])
@pytest.mark.parametrize("mixed_case", [False, True])
def test_original_wire_duplicate_rejected_before_dict_and_closed(monkeypatch, name, mixed_case):
    second = name.lower() if mixed_case else name
    sockets = install_wire(monkeypatch, raw_response(429, name + b": 9000\r\n" + second + b": 12\r\n"))
    gateway = create_network_gateway(NetworkPolicy(("api.github.com",)))
    with pytest.raises(NetworkPolicyViolation, match="duplicate rate-limit"):
        gateway.fetch(URL)
    assert len(sockets) == 1 and sockets[0].closed


@pytest.mark.parametrize("size", [129, 5000])
def test_overlength_wire_value_becomes_blocked_without_early_retry(monkeypatch, size):
    sockets = install_wire(monkeypatch, raw_response(429, b"Retry-After: " + b"9" * size + b"\r\n"))
    result = create_network_gateway(NetworkPolicy(("api.github.com",))).fetch(URL)
    failure = classify(result.status_code, result.redacted_headers)
    assert failure.blocked and failure.retry_after_seconds is None
    assert sockets[0].closed


def test_duplicate_link_keeps_existing_network_error(monkeypatch):
    sockets = install_wire(monkeypatch, raw_response(200, b"Link: <https://api.github.com/a>\r\nlink: <https://api.github.com/b>\r\n"))
    with pytest.raises(NetworkRequestError, match="duplicate response"):
        create_network_gateway(NetworkPolicy(("api.github.com",))).fetch(URL)
    assert sockets[0].closed


@pytest.mark.parametrize("status,headers,delay,blocked,code", [
    (401, {"Retry-After": "8"}, None, True, "source_auth_denied"),
    (403, {}, None, True, "source_auth_denied"),
    (429, {}, 30, False, "source_rate_limited"),
    (403, {"Retry-After": SHORT_DATE}, 9, False, "source_rate_limited"),
    (429, {"Retry-After": "300"}, 300, False, "source_rate_limited"),
    (429, {"Retry-After": "301"}, None, True, "source_rate_limited"),
    (429, {"Retry-After": "12, 9000"}, None, True, "source_rate_limited"),
    (403, {"x-ratelimit-remaining": "0"}, None, True, "source_rate_limited"),
    (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(NOW.timestamp()) + 60)}, 60, False, "source_rate_limited"),
    (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(NOW.timestamp()) + 301)}, None, True, "source_rate_limited"),
    (429, {"Retry-After": "Thu, 31 Feb 2026 12:35:05 GMT"}, None, True, "source_rate_limited"),
])
def test_independent_classification_table(status, headers, delay, blocked, code):
    failure = classify(status, headers)
    assert (failure.error_code, failure.retry_after_seconds, failure.blocked) == (code, delay, blocked)


@pytest.mark.parametrize("offset", [-11, 0, 9])
def test_absolute_date_compares_timezone_instants(offset):
    failure = classify(429, {"Retry-After": SHORT_DATE}, NOW.astimezone(timezone(timedelta(hours=offset))))
    assert failure.retry_after_seconds == 9


def test_replay_and_concurrent_clocks_preserve_response():
    headers = {"Retry-After": SHORT_DATE}
    with ThreadPoolExecutor(max_workers=4) as pool:
        failures = list(pool.map(lambda offset: classify(429, headers, NOW + timedelta(seconds=offset)), [0, 1, 2, 3]))
    assert [failure.retry_after_seconds for failure in failures] == [9, 8, 7, 7]
    assert classify(429, headers).retry_after_seconds == 9
    assert headers == {"Retry-After": SHORT_DATE}
    assert classify(429, headers, NOW.replace(tzinfo=None)).blocked


class Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str


@pytest.mark.parametrize("duplicate", [False, True])
def test_generation_actual_shared_post_transport_has_no_repair_on_duplicate(monkeypatch, duplicate):
    body = json.dumps({"id": "synthetic-independent-review", "model": "deepseek-flash", "object": "chat.completion",
                       "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"answer":"unknown"}'}}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}).encode()
    headers = b"Retry-After: 9\r\n" + (b"retry-after: 9000\r\n" if duplicate else b"")
    sockets = install_wire(monkeypatch, raw_response(200, headers, body))
    client = GenerationClient("deepseek_openai", "deepseek-flash", SecretStr("synthetic-review-only-no-real-account"))
    request = GenerationRequest(system_text="Use evidence.", question="What is known?", evidence_texts=("No supported fact.",), prompt_version="review-v1", schema_version="review-v1", model_version="deepseek-flash", max_output_tokens=100)
    if duplicate:
        with pytest.raises(GenerationFailure) as caught:
            client.generate(request, Reply)
        assert caught.value.code == "model_network_failure"
        assert len(caught.value.attempts) == 1
    else:
        assert client.generate(request, Reply).value.answer == "unknown"
    assert len(sockets) == 1 and sockets[0].closed
    assert b"POST " in b"".join(sockets[0].sent)


@pytest.mark.parametrize("status,headers,outcome,delay", [
    (429, {}, "retry_wait", 30),
    (429, {"Retry-After": SHORT_DATE}, "retry_wait", 9),
    (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(NOW.timestamp()) + 60)}, "retry_wait", 60),
    (403, {"x-ratelimit-remaining": "0"}, "blocked", None),
    (429, {"Retry-After": "9000"}, "blocked", None),
])
def test_pg_rate_failure_rolls_back_and_persists_safe_retry(job_engine, tmp_path, status, headers, outcome, delay):
    job_id = queue(job_engine)
    calls = []
    def fetch(url):
        calls.append(url)
        return FetchResult(url, status, "application/json", b"", headers)
    handler = build_source_page_handler(ContentStore(tmp_path), fetcher=fetch, clock=lambda: NOW)
    assert execute_job(job_engine, job_id, "independent-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW) == outcome
    assert execute_job(job_engine, job_id, "replay-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW) == "not_claimed"
    assert len(calls) == 1
    with Session(job_engine) as session:
        for table in (document_revisions, source_cursors, source_page_receipts):
            assert session.scalar(select(func.count()).select_from(table)) == 0
        row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
        assert row["error_code"] == "source_rate_limited" and row["status"] == outcome
        assert row["next_retry_at"] == (NOW + timedelta(seconds=delay) if delay else None)


def test_pg_original_duplicate_header_is_blocked_not_network_retry(monkeypatch, job_engine, tmp_path):
    sockets = install_wire(monkeypatch, raw_response(429, b"Retry-After: 9000\r\nRetry-After: 12\r\n"))
    job_id = queue(job_engine)
    handler = build_source_page_handler(ContentStore(tmp_path), clock=lambda: NOW)
    assert execute_job(job_engine, job_id, "wire-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW) == "blocked"
    with Session(job_engine) as session:
        row = session.execute(select(job_runs)).mappings().one()
        assert row["error_code"] == "source_network_policy_denied" and row["next_retry_at"] is None
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 0
    assert sockets[0].closed


def test_pg_failed_next_page_keeps_prior_receipt_and_cursor(job_engine, tmp_path):
    original = queue(job_engine)
    handler = build_source_page_handler(ContentStore(tmp_path), fetcher=lambda url: nvd_response(next_page=True), clock=lambda: NOW)
    assert execute_job(job_engine, original, "prior-page", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW) == "succeeded"
    with Session(job_engine) as session:
        cursor = dict(session.execute(select(source_cursors)).mappings().one())
        receipt = dict(session.execute(select(source_page_receipts)).mappings().one())
        following = session.scalar(select(job_runs.c.job_id).where(job_runs.c.job_id != original))
    later = NOW + timedelta(seconds=7)
    failed = build_source_page_handler(ContentStore(tmp_path), fetcher=lambda url: FetchResult(url, 429, "", b"", {"Retry-After": "9000"}), clock=lambda: later)
    assert execute_job(job_engine, following, "limited-page", {SOURCE_JOB_TYPE: failed}, clock=lambda: later) == "blocked"
    with Session(job_engine) as session:
        assert dict(session.execute(select(source_cursors)).mappings().one()) == cursor
        assert dict(session.execute(select(source_page_receipts)).mappings().one()) == receipt
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 1


def test_pg_two_workers_only_one_fetch_and_one_safe_failure(job_engine, tmp_path):
    job_id = queue(job_engine)
    entered, release = Event(), Event()
    calls = []
    def fetch(url):
        calls.append(url)
        entered.set()
        assert release.wait(5)
        return FetchResult(url, 429, "", b"", {"Retry-After": "17"})
    handler = build_source_page_handler(ContentStore(tmp_path), fetcher=fetch, clock=lambda: NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(execute_job, job_engine, job_id, "worker-one", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW)
        assert entered.wait(5)
        try:
            second = pool.submit(execute_job, job_engine, job_id, "worker-two", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW)
            assert second.result(timeout=5) == "not_claimed"
        finally:
            release.set()
        assert first.result(timeout=5) == "retry_wait"
    assert len(calls) == 1
    with Session(job_engine) as session:
        row = session.execute(select(job_runs)).mappings().one()
        assert row["attempt_count"] == 1 and row["next_retry_at"] == NOW + timedelta(seconds=17)
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 0
