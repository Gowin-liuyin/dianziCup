"""Socket 超时即使早于粗粒度 deadline 时钟也必须保留准确故障类型。"""

import io

import pytest
from test_r03_network_transport import FixtureSocket, _install_socket_fixtures, _response

from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkTimeoutError,
    create_network_gateway,
)


@pytest.mark.parametrize("operation", ["connect", "do_handshake", "read", "dns"])
def test_socket_timeout_is_not_misclassified_as_generic_network_failure(monkeypatch, operation):
    sockets, _ = _install_socket_fixtures(monkeypatch, [_response()])

    def timed_out(*arguments, **keywords):
        raise TimeoutError("synthetic upstream diagnostic must not leak")

    if operation in {"connect", "do_handshake"}:
        monkeypatch.setattr(FixtureSocket, operation, timed_out)
    elif operation == "read":

        class TimedOutBody(io.BytesIO):
            def read(self, size=-1):
                raise TimeoutError("synthetic body timeout")

        monkeypatch.setattr(
            FixtureSocket, "makefile", lambda self, mode: TimedOutBody(self.response_bytes)
        )
    else:
        monkeypatch.setattr("ai_intel.infrastructure.http_transport.socket.getaddrinfo", timed_out)
    gateway = create_network_gateway(NetworkPolicy(("source.example",), total_timeout_seconds=10))
    with pytest.raises(NetworkTimeoutError) as caught:
        gateway.fetch("https://source.example/test")
    assert "synthetic" not in str(caught.value)
    assert all(connection.closed for connection in sockets)
