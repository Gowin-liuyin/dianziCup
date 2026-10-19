"""Independent synthetic fixtures; no product backend, credentials or paid calls."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from zoneinfo import ZoneInfo

import httpx
import pytest
from ai_intel_client.client import (
    MAX_RESPONSE_BYTES,
    ClientConfigurationError,
    ClientInputError,
    DianziApiError,
    DianziClient,
    DianziTransportError,
    ResponseContractError,
)
from ai_intel_client.models import (
    AskRequest,
    Citation,
    QAAnswer,
    StackCheckRequest,
    StackUploadRequest,
)
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import SecretStr, ValidationError
from r18_test_paths import ROOT, RUN

SDK = ROOT / "sdk/python"
ID = "00000000-0000-4000-8000-000000000001"
SYNTHETIC_KEY = "synthetic-independent-test-key-no-provider-access"
QUESTION = {"question": "synthetic review question", "mode": "library"}
COMPONENT = {"ecosystem": "PyPI", "package_name": "review-fixture", "version": None}
ANSWER = {
    "kind": "completed",
    "answer_id": ID,
    "answer_text": "证据不足；🙂",
    "claims": [],
    "citations": [],
    "limitations": ["synthetic fixture only"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}
TASK = {
    "kind": "task",
    "task_id": ID,
    "status": "queued",
    "poll_uri": "/api/v1/tasks/" + ID,
    "created_at": "2026-10-16T00:00:00Z",
}
CITATION = {
    "evidence_id": ID,
    "revision_id": ID,
    "quote": "synthetic",
    "locator": "paragraph:1",
    "source_uri": "https://example.org/fixture",
}
SCHEMA = json.loads((ROOT / "contracts/schemas/public_api_v2.json").read_bytes())
HTTP_REQUEST_COUNT = 0


@pytest.fixture(scope="session", autouse=True)
def record_bounded_fixture_network() -> Iterator[None]:
    started = datetime.now(ZoneInfo("Asia/Shanghai"))
    yield
    finished = datetime.now(ZoneInfo("Asia/Shanghai"))
    label = os.environ.get("REVIEW_RUN_LABEL", "unlabelled")
    record = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
        "temporary_loopback_requests": HTTP_REQUEST_COUNT,
        "request_limit": 100,
        "time_limit_seconds": 60,
        "product_network_requests": 0,
        "external_requests": 0,
        "credential_values_obtained": 0,
        "paid_requests": 0,
        "fixture_mode": "explicit synthetic temporary HTTPServer; no product integration",
    }
    assert HTTP_REQUEST_COUNT <= 100
    assert record["elapsed_seconds"] <= 60
    destination = RUN / f"{label}_network.json"
    assert not destination.exists()
    destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def approved_errors(name: str, value: object) -> list[object]:
    schema = {**SCHEMA, "$ref": f"#/$defs/{name}"}
    return list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value))


def client_for(response: httpx.Response) -> DianziClient:
    return DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: response),
    )


@pytest.mark.parametrize("invalid_id", [ID.replace("-", ""), "{" + ID + "}", "urn:uuid:" + ID])
def test_sdk_rejects_uuid_spellings_rejected_by_frozen_schema(invalid_id: str) -> None:
    value = {**CITATION, "evidence_id": invalid_id}
    assert approved_errors("Citation", value)
    with pytest.raises(ValidationError):
        Citation.model_validate_json(json.dumps(value))


@pytest.mark.parametrize(
    "invalid_time",
    [
        "2026-10-16 00:00:00Z",
        "2026-10-16T00:00:00+0800",
        "2026-10-16T00:00:00+08",
        "2026-10-16T00:00:00,123Z",
        "1760572800",
    ],
)
def test_sdk_rejects_non_rfc3339_time_rejected_by_frozen_schema(invalid_time: str) -> None:
    value = {**ANSWER, "started_at": invalid_time, "completed_at": invalid_time}
    assert approved_errors("QAAnswer", value)
    with pytest.raises(ValidationError):
        QAAnswer.model_validate_json(json.dumps(value))


@pytest.mark.parametrize(
    "field,value",
    [
        ("latency_milliseconds", True),
        ("latency_milliseconds", "1000"),
        ("latency_milliseconds", 1.5),
        ("answer_text", True),
        ("started_at", 1760572800),
        ("answer_id", 12),
        ("citations", {}),
        ("tenant_id", ID),
    ],
)
def test_strict_response_type_or_extra_boundary(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        QAAnswer.model_validate_json(json.dumps({**ANSWER, field: value}))


@pytest.mark.parametrize("value", [True, "1", 1.5])
def test_upload_count_and_size_never_coerce_bool_string_or_float(value: object) -> None:
    upload = {
        "upload_id": ID,
        "size_bytes": value,
        "declared_component_count": 1,
        "format": "json_components",
    }
    with pytest.raises(ValidationError):
        StackUploadRequest.model_validate_json(json.dumps(upload))


@pytest.mark.parametrize(
    "base",
    [
        "https://example.org/api",
        "https://example.org?x=1",
        "https://example.org#x",
        "https://user@example.org",
        "https://example.org:0",
        "https://example.org:65536",
        "https://example.org:-1",
        "https://example.org:\\123",
        " http://localhost:12345",
        "http://127.0.0.2:12345",
        "http://localhost.example.org",
        "https://example.org/../",
        "https://example.org/%2f",
        "https://example.org\n",
        "ftp://localhost",
    ],
)
def test_rejected_origin_cannot_reach_transport(base: str) -> None:
    calls = []
    transport = httpx.MockTransport(lambda request: calls.append(request))
    with pytest.raises(ClientConfigurationError):
        DianziClient(base, SecretStr(SYNTHETIC_KEY), transport=transport)
    assert calls == []


def test_proxy_ssl_and_other_account_fields_are_not_configuration_inputs(monkeypatch) -> None:
    monkeypatch.setenv("SSL_CERT_FILE", "D:/nonexistent-review-cert.pem")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    mapping = {
        "DIANZI_API_BASE_URL": "http://localhost:12345",
        "DIANZI_API_KEY": SYNTHETIC_KEY,
        "CODING_ACCOUNT_TOKEN": "synthetic-unrelated-account-secret",
    }
    with DianziClient.from_environment(mapping) as client:
        assert SYNTHETIC_KEY not in repr(client)
    with pytest.raises(ClientConfigurationError):
        DianziClient.from_environment({"CODING_ACCOUNT_TOKEN": SYNTHETIC_KEY})


@pytest.mark.parametrize(
    "content",
    [
        b'{"kind":"completed","claims":[{"kind":"source_fact","kind":"project_suggestion"}]}',
        b'{"latency_milliseconds":1e999}',
        b'{"number":-Infinity}',
        b'{"number":NaN}',
    ],
)
def test_nested_duplicate_and_nonfinite_wire_response_is_rejected(content: bytes) -> None:
    with (
        client_for(
            httpx.Response(200, content=content, headers={"content-type": "application/json"})
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.ask(AskRequest.model_validate_json(json.dumps(QUESTION)))


def test_stream_budget_stops_before_subsequent_chunks() -> None:
    consumed = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            for number in range(4):
                consumed.append(number)
                yield b" " * (MAX_RESPONSE_BYTES // 2)

    with (
        client_for(
            httpx.Response(200, stream=Stream(), headers={"content-type": "application/json"})
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.ask(AskRequest.model_validate_json(json.dumps(QUESTION)))
    assert consumed == [0, 1, 2]


def test_gzip_bomb_is_rejected_before_consumption() -> None:
    compressed = gzip.compress(b" " * (MAX_RESPONSE_BYTES * 2))
    consumed = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            consumed.append(True)
            yield compressed

    with (
        client_for(
            httpx.Response(200, stream=Stream(), headers={"content-encoding": "gzip"})
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.ask(AskRequest.model_validate_json(json.dumps(QUESTION)))
    assert consumed == []


def test_huge_single_component_is_schema_valid_but_engineering_cap_rejects_before_send() -> None:
    value = {"components": [{**COMPONENT, "package_name": "x" * MAX_RESPONSE_BYTES}]}
    assert not approved_errors("StackCheckRequest", value)
    request = StackCheckRequest.model_validate_json(json.dumps(value))
    calls = []
    with (
        DianziClient(
            "http://localhost:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(lambda r: calls.append(r)),
        ) as client,
        pytest.raises(ClientInputError),
    ):
        client.check_stack(request)
    assert calls == []


@pytest.mark.parametrize(
    "status,content",
    [
        (200, TASK),
        (202, ANSWER),
        (204, {}),
        (202, {"kind": "completed", "results": [], "limitations": []}),
    ],
)
def test_status_union_mismatch_does_not_become_success(status: int, content: object) -> None:
    with client_for(httpx.Response(status, json=content)) as client:
        expected = DianziApiError if status == 204 else ResponseContractError
        with pytest.raises(expected):
            client.ask(AskRequest.model_validate_json(json.dumps(QUESTION)))


@pytest.mark.parametrize("malformed", [False, True])
def test_problem_body_with_secret_has_safe_repr_and_traceback(malformed: bool) -> None:
    value = {
        "type": "urn:review:error",
        "title": SYNTHETIC_KEY,
        "status": 401,
        "detail": SYNTHETIC_KEY,
        "instance": SYNTHETIC_KEY,
        "trace_id": ID,
        "error": {
            "code": "unauthorized",
            "message": SYNTHETIC_KEY,
            "retryable": False,
            "details": {"secret": SYNTHETIC_KEY},
        },
    }
    if malformed:
        value["trace_id"] = SYNTHETIC_KEY
    with (
        client_for(
            httpx.Response(401, json=value, headers={"content-type": "application/problem+json"})
        ) as client,
        pytest.raises(DianziApiError) as caught,
    ):
        client.ask(AskRequest.model_validate_json(json.dumps(QUESTION)))
    assert SYNTHETIC_KEY not in str(caught.value) + repr(caught.value) + "".join(
        traceback.format_exception(caught.value)
    )
    assert caught.value.code == ("http_error" if malformed else "unauthorized")


def test_body_fingerprint_is_stable_for_input_key_order_and_backend_409_remains_failure() -> None:
    seen = {}
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body_hash = hashlib.sha256(request.content).hexdigest()
        key = request.headers["idempotency-key"]
        calls.append((key, body_hash))
        if key in seen and seen[key] != body_hash:
            return httpx.Response(409, content=b"synthetic conflict")
        seen[key] = body_hash
        return httpx.Response(200, json=ANSWER)

    with DianziClient(
        "http://localhost:12345", SecretStr(SYNTHETIC_KEY), transport=httpx.MockTransport(handler)
    ) as client:
        client.ask(AskRequest.model_validate_json(json.dumps(QUESTION)), idempotency_key="same-key")
        client.ask(
            AskRequest.model_validate_json(json.dumps(dict(reversed(list(QUESTION.items()))))),
            idempotency_key="same-key",
        )
        with pytest.raises(DianziApiError) as caught:
            client.ask(
                AskRequest(question="different body", mode="library"), idempotency_key="same-key"
            )
    assert calls[0] == calls[1]
    assert len(calls) == 3
    assert caught.value.status == 409


@contextmanager
def fixture_server(
    status: int, payload: bytes, *, headers: dict[str, str] | None = None, disconnect: bool = False
) -> Iterator[tuple[str, list[dict[str, object]]]]:
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_POST(self) -> None:
            global HTTP_REQUEST_COUNT
            HTTP_REQUEST_COUNT += 1
            assert HTTP_REQUEST_COUNT <= 100
            body = self.rfile.read(int(self.headers["Content-Length"]))
            calls.append(
                {
                    "path": self.path,
                    "body": body,
                    "cookie": self.headers.get("Cookie"),
                    "authorization_matches": self.headers.get("Authorization")
                    == "Bearer " + SYNTHETIC_KEY,
                }
            )
            if disconnect:
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(payload)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02))
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def run_cli(
    base: str, command: str, value: object, *, encoding: str = "utf-8"
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(SDK),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DIANZI_API_BASE_URL": base,
            "DIANZI_API_KEY": SYNTHETIC_KEY,
            "HTTP_PROXY": "http://127.0.0.1:1",
            "HTTPS_PROXY": "http://127.0.0.1:1",
            "ALL_PROXY": "http://127.0.0.1:1",
            "PYTHONIOENCODING": encoding,
        }
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_intel_client.cli",
            command,
            "--idempotency-key",
            "synthetic-review-operation",
        ],
        input=json.dumps(value).encode(),
        capture_output=True,
        cwd=ROOT,
        env=environment,
        timeout=10,
    )


@pytest.mark.parametrize("status,value", [(200, ANSWER), (202, TASK)])
def test_actual_cli_process_outputs_complete_json_and_exits_two(status: int, value: object) -> None:
    with fixture_server(status, json.dumps(value).encode()) as (base, calls):
        result = run_cli(base, "ask", QUESTION)
    assert result.returncode == 2
    assert json.loads(result.stdout) == value
    assert b"risk certainty" in result.stderr
    assert len(calls) == 1 and calls[0]["path"] == "/api/v1/ask"
    assert calls[0]["authorization_matches"] and calls[0]["cookie"] is None
    assert SYNTHETIC_KEY.encode() not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "state",
    [
        "supported_applicability",
        "excluded_with_evidence",
        "insufficient_evidence",
        "conflicting_evidence",
    ],
)
def test_actual_check_process_all_legacy_states_exit_two(state: str) -> None:
    value = {
        "kind": "completed",
        "results": [
            {
                "component": COMPONENT,
                "status": state,
                "reason_code": "synthetic_reason",
                "assessment_id": None,
                "citations": [],
                "freshness": "unknown",
            }
        ],
        "limitations": [],
    }
    with fixture_server(200, json.dumps(value).encode()) as (base, calls):
        result = run_cli(base, "check", {"components": [COMPONENT]})
    assert result.returncode == 2
    assert json.loads(result.stdout) == value
    assert calls[0]["path"] == "/api/v1/stack/check"


@pytest.mark.parametrize(
    "status,payload",
    [
        (401, b"synthetic-private-error"),
        (404, b"missing route"),
        (200, b"broken JSON"),
        (200, json.dumps(TASK).encode()),
    ],
)
def test_actual_cli_error_process_exits_three_without_stdout(status: int, payload: bytes) -> None:
    with fixture_server(status, payload) as (base, calls):
        result = run_cli(base, "ask", QUESTION)
    assert result.returncode == 3
    assert result.stdout == b""
    assert b"could not be completed" in result.stderr
    assert b"Traceback" not in result.stderr
    assert SYNTHETIC_KEY.encode() not in result.stderr
    assert len(calls) == 1


def test_raw_http_disconnection_is_one_call_and_unknown_execution() -> None:
    with (
        fixture_server(200, b"", disconnect=True) as (base, calls),
        DianziClient(base, SecretStr(SYNTHETIC_KEY)) as client,
        pytest.raises(DianziTransportError) as caught,
    ):
        client.ask(
            AskRequest.model_validate_json(json.dumps(QUESTION)),
            idempotency_key="original-key",
        )
    assert caught.value.may_have_executed is True
    assert caught.value.idempotency_key == "original-key"
    assert len(calls) == 1


def test_actual_cli_network_failure_exits_three_after_single_post() -> None:
    with fixture_server(200, b"", disconnect=True) as (base, calls):
        result = run_cli(base, "ask", QUESTION)
    assert result.returncode == 3
    assert result.stdout == b""
    assert b"Traceback" not in result.stderr
    assert len(calls) == 1


def test_raw_http_set_cookie_does_not_authenticate_second_post() -> None:
    with (
        fixture_server(
            200,
            json.dumps(ANSWER).encode(),
            headers={"Set-Cookie": "ai_intel_session=synthetic; Path=/"},
        ) as (base, calls),
        DianziClient(base, SecretStr(SYNTHETIC_KEY)) as client,
    ):
        request = AskRequest.model_validate_json(json.dumps(QUESTION))
        client.ask(request, idempotency_key="first")
        client.ask(request, idempotency_key="second")
    assert len(calls) == 2
    assert all(call["cookie"] is None and call["authorization_matches"] for call in calls)


def test_actual_cli_malformed_problem_secret_is_not_printed() -> None:
    problem = {
        "status": 401,
        "detail": SYNTHETIC_KEY,
        "error": {"message": SYNTHETIC_KEY, "retryable": "wrong-type"},
    }
    with fixture_server(
        401, json.dumps(problem).encode(), headers={"Content-Type": "application/problem+json"}
    ) as (base, calls):
        result = run_cli(base, "ask", QUESTION)
    assert result.returncode == 3
    assert result.stdout == b""
    assert SYNTHETIC_KEY.encode() not in result.stdout + result.stderr
    assert b"Traceback" not in result.stderr
    assert len(calls) == 1


def test_actual_cli_non_utf8_output_stream_still_returns_complete_json() -> None:
    with fixture_server(200, json.dumps(ANSWER).encode()) as (base, calls):
        result = run_cli(base, "ask", QUESTION, encoding="ascii")
    assert result.returncode == 2
    assert json.loads(result.stdout) == ANSWER
    assert len(calls) == 1


def test_actual_cli_oversized_input_is_failure_before_network() -> None:
    value = {"components": [{**COMPONENT, "package_name": "x" * MAX_RESPONSE_BYTES}]}
    with fixture_server(200, b"{}") as (base, calls):
        result = run_cli(base, "check", value)
    assert result.returncode == 3
    assert result.stdout == b"" and calls == []
