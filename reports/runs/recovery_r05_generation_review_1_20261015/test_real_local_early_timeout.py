"""Real local sockets produce early timeout with an absolute deadline still in the future."""

import socket
import ssl
import threading
import time
from contextlib import suppress

import pytest

from ai_intel.infrastructure import http_transport
from ai_intel.infrastructure.network import NetworkPolicy, NetworkTimeoutError, create_network_gateway


@pytest.mark.parametrize('phase', ['headers', 'body', 'tls_handshake'])
def test_real_socket_timeout_before_timer_remains_timeout(monkeypatch, phase):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(1)
    accepted = threading.Event()
    sent = []
    errors = []
    def serve():
        try:
            peer, _address = listener.accept()
            with peer:
                accepted.set()
                peer.settimeout(1)
                if phase == 'tls_handshake':
                    peer.recv(4096)
                else:
                    sent.append(peer.recv(4096))
                    if phase == 'body':
                        peer.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 4\r\n\r\n{')
                time.sleep(.12)
        except Exception as error:
            errors.append(type(error).__name__)
    thread = threading.Thread(target=serve)
    thread.start()
    def connect(connection):
        raw = socket.create_connection(listener.getsockname(), timeout=.025)
        connection.sock = raw
        connection._active_socket = raw
        if phase == 'tls_handshake':
            tls = connection._tls_context.wrap_socket(raw, server_hostname=connection.host, do_handshake_on_connect=False)
            connection.sock = connection._active_socket = tls
            tls.settimeout(.025)
            tls.do_handshake()
    monkeypatch.setattr(http_transport._PinnedConnection, 'connect', connect)
    gateway = create_network_gateway(NetworkPolicy(('source.example',), total_timeout_seconds=3.0))
    monkeypatch.setattr(gateway._transport, 'resolve_addresses', lambda host, deadline: ['93.184.216.34'])
    began = time.perf_counter()
    try:
        with pytest.raises(NetworkTimeoutError) as caught:
            gateway.post_json('https://source.example/test', b'{}')
        assert accepted.is_set()
        assert .015 < time.perf_counter() - began < 1.0
        assert 'synthetic' not in str(caught.value)
        if phase != 'tls_handshake':
            assert sent[0].startswith(b'POST /test HTTP/1.1')
    finally:
        listener.close()
        thread.join(2)
        assert not thread.is_alive()
        assert errors == []
