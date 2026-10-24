"""真实http.client/本地socket协议验证；fixture仅替换DNS与TLS连接，不计供应商live。"""

import json
import socket
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from pydantic import SecretStr
from tests.unit.test_r05_generation import Answer, request, wire

from ai_intel.infrastructure import http_transport
from ai_intel.infrastructure.models.generation import (
    GenerationClient,
    GenerationFailure,
    GenerationLimits,
)


@pytest.fixture()
def isolated_http(monkeypatch):
    captured = []
    controls = {"status": 200, "delay": 0.0, "provider": "deepseek_openai"}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = self.rfile.read(int(self.headers["Content-Length"]))
            captured.append(
                {"path": self.path, "headers": dict(self.headers), "body": json.loads(payload)}
            )
            time.sleep(controls["delay"])
            status = controls["status"]
            encoded = json.dumps(wire(controls["provider"])).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            if status == 302:
                self.send_header("Location", "https://api.openai.com/v1/chat/completions")
            self.end_headers()
            with suppress(BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.wfile.write(encoded)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever)
    thread.start()

    def connect(connection):
        connection.sock = socket.create_connection(
            server.server_address, timeout=connection._deadline.remaining_seconds()
        )
        connection._active_socket = connection.sock

    monkeypatch.setattr(http_transport._PinnedConnection, "connect", connect)
    try:
        yield captured, controls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        assert not thread.is_alive()


def client(monkeypatch, provider="deepseek_openai", timeout=2.0):
    result = GenerationClient(
        provider,
        "deepseek-flash",
        SecretStr("fixture-http-generation-key"),
        limits=GenerationLimits(total_timeout_seconds=timeout),
    )
    monkeypatch.setattr(
        result._gateway._transport, "resolve_addresses", lambda host, deadline: ["8.8.8.8"]
    )
    return result


@pytest.mark.parametrize("provider", ["deepseek_openai", "deepseek_anthropic"])
def test_real_http_wire_headers_and_completion(isolated_http, monkeypatch, provider):
    captured, controls = isolated_http
    controls["provider"] = provider
    result = client(monkeypatch, provider).generate(request(), Answer)
    assert result.value.answer == "unknown"
    assert len(captured) == 1
    packet = captured[0]
    assert packet["headers"]["Host"] == "api.deepseek.com"
    assert packet["headers"]["Content-Type"] == "application/json"
    if provider.endswith("anthropic"):
        assert packet["path"] == "/anthropic/v1/messages"
        assert packet["headers"]["x-api-key"] == "fixture-http-generation-key"
        assert packet["headers"]["anthropic-version"] == "2023-06-01"
    else:
        assert packet["path"] == "/chat/completions"
        assert packet["headers"]["Authorization"] == "Bearer fixture-http-generation-key"
    assert "fixture-http-generation-key" not in json.dumps(packet["body"])
    assert "fixture-http-generation-key" not in repr(result.attempts)


@pytest.mark.parametrize("status", [401, 429, 503, 302])
def test_real_http_error_and_redirect_never_second_request(isolated_http, monkeypatch, status):
    captured, controls = isolated_http
    controls["status"] = status
    with pytest.raises(GenerationFailure) as failure:
        client(monkeypatch).generate(request(allow_format_repair=True), Answer)
    assert len(captured) == 1
    assert len(failure.value.attempts) == 1
    if status != 302:
        assert failure.value.attempts[0].http_status == status
    else:
        assert failure.value.code == "model_network_failure"


def test_real_http_timeout_reports_complete_duration(isolated_http, monkeypatch):
    captured, controls = isolated_http
    controls["delay"] = 0.2
    started = time.monotonic()
    with pytest.raises(GenerationFailure) as failure:
        client(monkeypatch, timeout=0.05).generate(request(allow_format_repair=True), Answer)
    assert failure.value.code == "model_network_timeout"
    assert len(captured) == 1
    assert 0.04 <= time.monotonic() - started < 0.5
    assert failure.value.attempts[0].elapsed_milliseconds >= 40
