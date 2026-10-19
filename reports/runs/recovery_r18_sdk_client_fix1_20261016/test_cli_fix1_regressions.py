"""Reuse the unchanged review fixture for real subprocess encoding and rejection paths."""

from __future__ import annotations

import io
import json

import httpx
import pytest
from ai_intel_client.cli import main
from ai_intel_client.client import DianziClient
from pydantic import SecretStr
from test_independent_boundaries import (
    ANSWER,
    COMPONENT,
    ID,
    QUESTION,
    SYNTHETIC_KEY,
    TASK,
    fixture_server,
    run_cli,
)

INTERNATIONAL_COMPONENT = dict(COMPONENT, package_name="合法组件🙂")
STACK = {
    "kind": "completed",
    "results": [
        {
            "component": INTERNATIONAL_COMPONENT,
            "status": "insufficient_evidence",
            "reason_code": "no_match",
            "assessment_id": None,
            "citations": [],
            "freshness": "unknown",
        }
    ],
    "limitations": ["原文证据不足；🙂"],
}


@pytest.mark.parametrize("encoding", ["ascii", "utf-8"])
@pytest.mark.parametrize(
    "command,status,input_value,response",
    [
        ("ask", 200, QUESTION, ANSWER),
        ("ask", 202, QUESTION, TASK),
        ("check", 200, {"components": [INTERNATIONAL_COMPONENT]}, STACK),
    ],
)
def test_actual_cli_output_preserves_complete_unicode_json_and_uncertainty(
    encoding: str, command: str, status: int, input_value: object, response: object
) -> None:
    with fixture_server(status, json.dumps(response).encode("utf-8")) as (base, calls):
        result = run_cli(base, command, input_value, encoding=encoding)
    assert result.returncode == 2
    assert json.loads(result.stdout) == response
    assert len(result.stdout) > 0 and len(calls) == 1
    assert b"Traceback" not in result.stderr
    assert b"could not be completed" not in result.stderr
    assert SYNTHETIC_KEY.encode() not in result.stdout + result.stderr
    assert result.stdout.isascii()
    assert result.stdout.count(b"\n") == 1


@pytest.mark.parametrize("encoding", ["ascii", "utf-8"])
def test_actual_cli_execution_failure_stays_three_with_no_stdout(encoding: str) -> None:
    with fixture_server(401, b"synthetic forbidden private body") as (base, calls):
        result = run_cli(base, "ask", QUESTION, encoding=encoding)
    assert result.returncode == 3
    assert result.stdout == b"" and len(calls) == 1
    assert b"Traceback" not in result.stderr
    assert b"private body" not in result.stderr


@pytest.mark.parametrize(
    "input_value",
    [dict(QUESTION, event_ids=[ID.replace("-", "")]), dict(QUESTION, known_at="1760572800")],
)
def test_actual_cli_invalid_wire_formats_fail_before_http(input_value: object) -> None:
    with fixture_server(200, json.dumps(ANSWER).encode("utf-8")) as (base, calls):
        result = run_cli(base, "ask", input_value, encoding="ascii")
    assert result.returncode == 3
    assert result.stdout == b"" and calls == []
    assert b"Traceback" not in result.stderr


class BrokenOutput(io.StringIO):
    def write(self, text: str) -> int:
        raise BrokenPipeError("synthetic output sink closed")


def test_output_sink_failure_returns_execution_three_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def client_factory() -> DianziClient:
        return DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
        )

    monkeypatch.setattr(DianziClient, "from_environment", client_factory)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(json.dumps(QUESTION).encode())))
    monkeypatch.setattr("sys.stdout", BrokenOutput())
    assert main(["ask"]) == 3
    assert "Traceback" not in capsys.readouterr().err
