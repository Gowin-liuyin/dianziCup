"""The CLI displays only typed actual responses and conservatively preserves uncertainty."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from ai_intel_client.cli import main
from ai_intel_client.client import DianziClient
from pydantic import SecretStr

SYNTHETIC_KEY = "synthetic-test-key-with-no-provider-access"


def install_fixture_client(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> list[httpx.Request]:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return response

    def factory() -> DianziClient:
        return DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(DianziClient, "from_environment", factory)
    return calls


@pytest.mark.parametrize(
    "state",
    [
        "supported_applicability",
        "excluded_with_evidence",
        "insufficient_evidence",
        "conflicting_evidence",
    ],
)
def test_legacy_stack_without_risk_confirmation_is_never_zero_or_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], state: str
) -> None:
    component = {"ecosystem": "PyPI", "package_name": "synthetic-package", "version": "1.0.0"}
    result = {
        "kind": "completed",
        "results": [
            {
                "component": component,
                "status": state,
                "reason_code": "synthetic_boundary",
                "assessment_id": None,
                "citations": [],
                "freshness": "current",
            }
        ],
        "limitations": [],
    }
    source = tmp_path / "synthetic-stack.json"
    source.write_text(json.dumps({"components": [component]}))
    calls = install_fixture_client(monkeypatch, httpx.Response(200, json=result))
    assert main(["check", "--input", str(source)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result
    assert "uncertainty" in captured.err
    assert SYNTHETIC_KEY not in captured.out + captured.err
    assert len(calls) == 1
    assert calls[0].url.path == "/api/v1/stack/check"


def test_async_ask_does_not_report_completed_or_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    task_id = "00000000-0000-4000-8000-000000000001"
    task = {
        "kind": "task",
        "task_id": task_id,
        "status": "queued",
        "poll_uri": "/api/v1/tasks/" + task_id,
        "created_at": "2026-10-16T00:00:00Z",
    }
    source = tmp_path / "synthetic-question.json"
    source.write_text(json.dumps({"question": "synthetic question", "mode": "library"}))
    install_fixture_client(monkeypatch, httpx.Response(202, json=task))
    assert main(["ask", "--input", str(source)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["kind"] == "task"
    assert "answer_text" not in json.loads(captured.out)


@pytest.mark.parametrize("status", [401, 403, 404, 409, 429, 503])
def test_http_failure_is_three_and_does_not_print_server_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], status: int
) -> None:
    source = tmp_path / "synthetic-question.json"
    source.write_text(json.dumps({"question": "synthetic question", "mode": "library"}))
    install_fixture_client(
        monkeypatch, httpx.Response(status, content=b"SYNTHETIC_PRIVATE_SERVER_BODY")
    )
    assert main(["ask", "--input", str(source)]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "SYNTHETIC_PRIVATE" not in captured.err
    assert SYNTHETIC_KEY not in captured.err


@pytest.mark.parametrize(
    "content",
    [
        b'{"question":"synthetic","question":"duplicated","mode":"library"}',
        b'{"question":"synthetic","mode":"library","tenant_id":"forged"}',
        b'{"question":"synthetic","mode":"library","known_at":null}',
    ],
)
def test_invalid_input_never_calls_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    content: bytes,
) -> None:
    source = tmp_path / "synthetic-invalid.json"
    source.write_bytes(content)
    calls = install_fixture_client(monkeypatch, httpx.Response(200, json={}))
    assert main(["ask", "--input", str(source)]) == 3
    assert calls == []
    assert capsys.readouterr().out == ""


def test_unknown_arguments_cannot_echo_an_accidentally_supplied_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check", "--api-key", SYNTHETIC_KEY]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert SYNTHETIC_KEY not in captured.err


def test_missing_configuration_is_three_without_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DIANZI_API_BASE_URL", raising=False)
    monkeypatch.delenv("DIANZI_API_KEY", raising=False)
    source = tmp_path / "synthetic-stack.json"
    source.write_text('{"components":[]}')
    assert main(["check", "--input", str(source)]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "could not be completed" in captured.err
