"""Isolated socket fixtures exercise the real gateway without live provider requests."""

import json
import threading
import time
from datetime import datetime

import pytest
from pydantic import SecretStr
from test_r03_network_transport import _install_socket_fixtures

from ai_intel.assets.aggregate_observations import MAX_RESPONSE_BYTES
from ai_intel.assets.hunter_aggregate import HunterAggregateConnector
from ai_intel.assets.quake_aggregate import QuakeAggregateConnector

CONNECTORS = (HunterAggregateConnector, QuakeAggregateConnector)


def socket_response(status: int, body: bytes, headers: bytes = b"") -> bytes:
    return (
        f"HTTP/1.1 {status} Fixture\r\nContent-Type: application/json\r\n".encode()
        + headers
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )


def success_body(connector_type) -> bytes:
    return (
        b'{"code":200,"data":{"total":7,"arr":[{"ip":"192.0.2.42","banner":"private"}]}}'
        if connector_type is HunterAggregateConnector
        else b'{"code":0,"meta":{"pagination":{"total":7}},"data":[{"ip":"192.0.2.42"}]}'
    )


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_real_wire_uses_only_fixed_origin_and_discards_details(monkeypatch, connector_type) -> None:
    sockets, queries = _install_socket_fixtures(
        monkeypatch, [socket_response(200, success_body(connector_type))]
    )
    connector = connector_type(SecretStr("synthetic-r08-api-key"))
    result = connector.collect("ollama")
    sent = b"".join(sockets[0].sent)
    expected_origin = (
        "hunter.qianxin.com" if connector_type is HunterAggregateConnector else "quake.360.net"
    )
    assert queries == [expected_origin]
    assert sockets[0].sni == expected_origin
    assert b"synthetic-r08-api-key" in sent
    if connector_type is HunterAggregateConnector:
        assert sent.startswith(b"GET /openApi/search?")
        assert b"api-key=synthetic-r08-api-key" in sent
    else:
        assert sent.startswith(b"POST /api/v3/search/quake_service ")
        assert b"X-QuakeToken: synthetic-r08-api-key" in sent
        assert json.loads(sent.split(b"\r\n\r\n", 1)[1]) == {
            "query": 'app:"Ollama"',
            "start": 0,
            "size": 1,
        }
    assert sockets[0].closed
    assert result.outcome == "available"
    assert result.data_mode == "live"
    serialized = result.model_dump_json()
    assert "synthetic-r08-api-key" not in serialized
    assert "192.0.2.42" not in serialized
    assert "private" not in serialized


@pytest.mark.parametrize("connector_type", CONNECTORS)
@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect_never_sends_secret_to_another_origin(
    monkeypatch, connector_type, status: int
) -> None:
    sockets, queries = _install_socket_fixtures(
        monkeypatch, [socket_response(status, b"", b"Location: https://other.example/receive\r\n")]
    )
    result = connector_type(SecretStr("synthetic-r08-api-key")).collect("ollama")
    assert result.error_code == "network_policy_violation"
    assert result.value is None
    assert len(sockets) == len(queries) == 1
    assert sockets[0].closed


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_oversized_response_is_bounded_and_not_retried(monkeypatch, connector_type) -> None:
    sockets, queries = _install_socket_fixtures(
        monkeypatch, [socket_response(200, b"x" * (MAX_RESPONSE_BYTES + 1))]
    )
    result = connector_type(SecretStr("synthetic-r08-api-key")).collect("ollama")
    assert (result.outcome, result.error_code, result.value) == (
        "failed",
        "response_too_large",
        None,
    )
    assert len(sockets) == len(queries) == 1
    assert sockets[0].closed


@pytest.mark.parametrize("connector_type", CONNECTORS)
@pytest.mark.parametrize(
    "query_id", ["", "other", 'ollama" || ip="0.0.0.0/0', "https://example.invalid", None]
)
def test_invalid_query_stops_before_dns(monkeypatch, connector_type, query_id) -> None:
    sockets, queries = _install_socket_fixtures(monkeypatch, [])
    with pytest.raises(ValueError, match="query_id"):
        connector_type(SecretStr("synthetic-r08-api-key")).collect(query_id)
    assert sockets == queries == []


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_live_retrieval_clock_cannot_be_overridden(monkeypatch, connector_type) -> None:
    sockets, queries = _install_socket_fixtures(monkeypatch, [])
    with pytest.raises(ValueError, match="explicit fixture mode"):
        connector_type(SecretStr("synthetic-r08-api-key")).collect(
            "ollama", retrieved_at=datetime(2026, 10, 16)
        )
    assert sockets == queries == []


@pytest.mark.parametrize("connector_type", CONNECTORS)
@pytest.mark.parametrize(
    "api_key", [SecretStr(""), SecretStr("x\r\n"), SecretStr("x" * 4097), "raw-key"]
)
def test_invalid_credential_is_rejected_without_dns(monkeypatch, connector_type, api_key) -> None:
    sockets, queries = _install_socket_fixtures(monkeypatch, [])
    with pytest.raises(ValueError, match="bounded SecretStr"):
        connector_type(api_key)
    assert sockets == queries == []


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_fixture_cannot_receive_a_live_credential(connector_type) -> None:
    with pytest.raises(ValueError, match="fixture mode"):
        connector_type(SecretStr("synthetic-r08-api-key"), fixture_gateway=object())


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_one_connector_serializes_its_gateway_requests(monkeypatch, connector_type) -> None:
    from ai_intel.infrastructure.http_transport import PinnedHttpTransport

    connector = connector_type(SecretStr("synthetic-r08-api-key"))
    active_requests = 0
    maximum_active = 0
    calls = 0
    lock = threading.Lock()
    entered = threading.Event()

    def bounded_fixture(self, url, addresses, deadline, headers, **kwargs):
        nonlocal active_requests, maximum_active, calls
        with lock:
            active_requests += 1
            maximum_active = max(maximum_active, active_requests)
            calls += 1
        entered.set()
        time.sleep(0.02)
        with lock:
            active_requests -= 1
        document = success_body(connector_type)

        class Response:
            status_code = 200

            def __init__(self) -> None:
                self.headers = {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(document)),
                }

            def iter_bytes(self):
                yield document

            def close(self):
                pass

        return Response()

    monkeypatch.setattr(PinnedHttpTransport, "request", bounded_fixture)
    monkeypatch.setattr(PinnedHttpTransport, "resolve_addresses", lambda *args: ["93.184.216.34"])
    observations = []
    workers = [
        threading.Thread(target=lambda: observations.append(connector.collect("ollama")))
        for _ in range(3)
    ]
    for worker in workers:
        worker.start()
    assert entered.wait(1)
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()
    assert maximum_active == 1
    assert calls == len(observations) == 3
    assert all(observation.outcome == "available" for observation in observations)
