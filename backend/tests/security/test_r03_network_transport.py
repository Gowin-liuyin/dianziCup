"""R03 real factory uses isolated socket fixtures; these do not count as live probes."""

from __future__ import annotations

import hashlib
import http.client
import io
import socket
import ssl
import threading
import time
import traceback

import pytest
from pydantic import SecretStr

from ai_intel.infrastructure import http_transport
from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkRequestError,
    NetworkTimeoutError,
    OriginCredentials,
    RequestDeadline,
    classify_http_failure,
    create_network_gateway,
    fetch_with_policy,
    redact_headers,
    redact_url,
)


class FixtureSocket:
    def __init__(self, response_bytes: bytes, peer: str = "93.184.216.34") -> None:
        self.response_bytes = response_bytes
        self.peer = peer
        self.connected: tuple[str, int] | None = None
        self.sent: list[bytes] = []
        self.closed = False
        self.shutdown_called = False
        self.timeout = 0.0
        self.sni = ""
        self.handshakes = 0

    def connect(self, target: tuple[str, int]) -> None:
        self.connected = target

    def getpeername(self) -> tuple[str, int]:
        return self.peer, 443

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendall(self, value: bytes) -> None:
        self.sent.append(value)

    def makefile(self, mode: str) -> io.BytesIO:
        return io.BytesIO(self.response_bytes)

    def do_handshake(self) -> None:
        self.handshakes += 1

    def close(self) -> None:
        self.closed = True

    def shutdown(self, how: int) -> None:
        self.shutdown_called = True


def _response(status: int = 200, headers: bytes = b"", body: bytes = b"document") -> bytes:
    return (
        f"HTTP/1.1 {status} Fixture\r\nContent-Type: text/plain\r\n".encode()
        + headers
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )


def _install_socket_fixtures(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[bytes],
) -> tuple[list[FixtureSocket], list[str]]:
    sockets: list[FixtureSocket] = []
    dns_queries: list[str] = []

    def resolve(host: str, port: object, **options: object) -> list[tuple[object, ...]]:
        dns_queries.append(host)
        address = "93.184.216.34" if len(dns_queries) <= len(responses) else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    def create_socket(*arguments: object) -> FixtureSocket:
        result = FixtureSocket(responses[len(sockets)])
        sockets.append(result)
        return result

    def wrap_socket(
        context: ssl.SSLContext,
        connection: FixtureSocket,
        *,
        server_hostname: str,
        do_handshake_on_connect: bool,
    ) -> FixtureSocket:
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        assert do_handshake_on_connect is False
        connection.sni = server_hostname
        return connection

    monkeypatch.setattr(http_transport.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(http_transport.socket, "socket", create_socket)
    monkeypatch.setattr(http_transport.ssl.SSLContext, "wrap_socket", wrap_socket)
    return sockets, dns_queries


def test_real_factory_pins_checked_ip_preserves_sni_host_and_ignores_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets, queries = _install_socket_fixtures(monkeypatch, [_response()])
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:8080")
    result = fetch_with_policy(
        NetworkPolicy(("source.example",)), "https://source.example/document"
    )
    assert result.body == b"document"
    assert queries == ["source.example"]
    assert sockets[0].connected == ("93.184.216.34", 443)
    assert sockets[0].sni == "source.example"
    assert sockets[0].handshakes == 1
    assert b"Host: source.example\r\n" in b"".join(sockets[0].sent)
    assert sockets[0].closed


def test_changed_peer_is_rejected_before_tls_or_http(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_socket = FixtureSocket(_response(), peer="127.0.0.1")
    monkeypatch.setattr(http_transport.socket, "socket", lambda *args: fixture_socket)
    transport = http_transport.PinnedHttpTransport(100, 1)
    with pytest.raises(NetworkPolicyViolation, match="peer"):
        transport.request(
            "https://source.example/", ("93.184.216.34",), RequestDeadline(time.monotonic() + 1), {}
        )
    assert fixture_socket.sent == []
    assert fixture_socket.closed


def test_relative_redirect_rechecks_dns_and_never_forwards_cross_origin_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets, queries = _install_socket_fixtures(
        monkeypatch,
        [
            _response(302, b"Location: ../second\r\n", b""),
            _response(302, b"Location: https://other.example/final\r\n", b""),
            _response(),
        ],
    )
    credentials = OriginCredentials(
        "https://source.example",
        headers={
            "Authorization": SecretStr("Bearer synthetic-sensitive-value"),
            "Cookie": SecretStr("session=synthetic-sensitive-value"),
        },
        query_parameters={"api-key": SecretStr("synthetic-sensitive-value")},
    )
    gateway = create_network_gateway(
        NetworkPolicy(("source.example", "other.example")), credentials
    )
    result = gateway.fetch("https://source.example/dir/start")
    assert queries == ["source.example", "source.example", "other.example"]
    assert b"GET /second?api-key=synthetic-sensitive-value HTTP/1.1" in b"".join(sockets[1].sent)
    assert b"Authorization:" in b"".join(sockets[0].sent)
    assert b"Cookie:" in b"".join(sockets[1].sent)
    assert b"synthetic-sensitive-value" not in b"".join(sockets[2].sent)
    assert result.final_url == "https://other.example/final"
    assert all(response.closed for response in sockets)
    assert "synthetic-sensitive-value" not in repr(credentials)


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_real_transport_does_not_retry_statuses(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    sockets, queries = _install_socket_fixtures(monkeypatch, [_response(status)])
    result = create_network_gateway(NetworkPolicy(("source.example",))).fetch(
        "https://source.example/"
    )
    assert result.status_code == status
    assert len(queries) == len(sockets) == 1
    assert sockets[0].closed
    assert classify_http_failure(429) == "rate_limited"
    assert classify_http_failure(401) == "permanent_auth_error"


@pytest.mark.parametrize(
    "url",
    [
        "http://source.example/",
        "https://source.example:8443/",
        "https://user:password@source.example/",
        "https://source.example:invalid/",
        "https://source.example/\r\napi-key=synthetic-sensitive-value",
        "https://source.example.evil/",
        "https://source.example/文件?api-key=synthetic-sensitive-value",
        "https://sub\\.source.example/",
    ],
)
def test_url_boundaries_reject_before_dns_without_echoing_input(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
) -> None:
    sockets, queries = _install_socket_fixtures(monkeypatch, [])
    with pytest.raises(NetworkPolicyViolation) as captured:
        create_network_gateway(NetworkPolicy(("source.example",))).fetch(url)
    assert queries == sockets == []
    assert "synthetic-sensitive-value" not in str(captured.value)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "224.0.0.1",
        "::1",
        "::ffff:127.0.0.1",
        "100.64.0.1",
    ],
)
def test_nonpublic_dns_is_rejected_before_connect(
    monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    sockets, _queries = _install_socket_fixtures(monkeypatch, [])
    monkeypatch.setattr(
        http_transport.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0)),
        ],
    )
    with pytest.raises(NetworkPolicyViolation):
        create_network_gateway(NetworkPolicy(("source.example",))).fetch("https://source.example/")
    assert sockets == []


@pytest.mark.parametrize(
    "key", ["api-key", "api_key", "Authorization", "cookie", "X-QuakeToken", "X-API-Key"]
)
def test_secret_redaction_matches_query_and_header_case(key: str) -> None:
    secret = "synthetic-sensitive-value"
    url = f"https://source.example/?{key}={secret}&visible=1"
    redacted, fingerprint = redact_url(url)
    assert secret not in redacted
    assert "visible=1" in redacted
    assert fingerprint == hashlib.sha256(url.encode()).hexdigest()
    assert redact_headers({key: secret})[key] == "REDACTED"


@pytest.mark.parametrize("operation", ["dns", "send", "headers", "tls"])
def test_transport_errors_and_tracebacks_never_include_credential_values(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    sockets, _queries = _install_socket_fixtures(monkeypatch, [_response()])
    secret = "synthetic-sensitive-value"

    def fail(*args: object, **kwargs: object) -> None:
        if operation == "tls":
            raise ssl.SSLCertVerificationError(secret)
        if operation == "headers":
            raise http.client.BadStatusLine(secret)
        raise OSError(secret)

    if operation == "dns":
        monkeypatch.setattr(http_transport.socket, "getaddrinfo", fail)
    elif operation == "send":
        monkeypatch.setattr(FixtureSocket, "sendall", fail)
    elif operation == "headers":
        monkeypatch.setattr(http.client.HTTPConnection, "getresponse", fail)
    else:
        monkeypatch.setattr(FixtureSocket, "do_handshake", fail)
    credentials = OriginCredentials("https://source.example", {"api-key": SecretStr(secret)})
    with pytest.raises(NetworkRequestError) as captured:
        create_network_gateway(NetworkPolicy(("source.example",)), credentials).fetch(
            "https://source.example/"
        )
    assert secret not in "".join(traceback.format_exception(captured.value))
    expected_code = {
        "dns": "network_dns_error",
        "tls": "network_tls_error",
        "send": "network_error",
        "headers": "network_error",
    }
    assert captured.value.code == expected_code[operation]
    assert all(connection.closed for connection in sockets)


def test_dns_timeout_is_bounded_and_outstanding_resolution_does_not_accumulate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    resolver_calls: list[str] = []

    def stalled_dns(host: str, *args: object, **kwargs: object) -> list[object]:
        resolver_calls.append(host)
        entered.set()
        release.wait(2)
        return []

    monkeypatch.setattr(http_transport.socket, "getaddrinfo", stalled_dns)
    gateway = create_network_gateway(
        NetworkPolicy(("source.example",), total_timeout_seconds=0.03), max_concurrent_requests=1
    )
    started = time.monotonic()
    try:
        for _ in range(3):
            with pytest.raises(NetworkTimeoutError):
                gateway.fetch("https://source.example/")
        assert entered.is_set()
        assert resolver_calls == ["source.example"]
        assert time.monotonic() - started < 1
    finally:
        release.set()


def test_request_concurrency_wait_uses_the_same_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    gateway = create_network_gateway(
        NetworkPolicy(("source.example",), total_timeout_seconds=0.04), max_concurrent_requests=1
    )
    failures: list[str] = []

    def block(host: str, deadline: RequestDeadline) -> list[str]:
        entered.set()
        release.wait(1)
        deadline.remaining_seconds()
        return ["93.184.216.34"]

    monkeypatch.setattr(gateway._transport, "resolve_addresses", block)

    def fetch() -> None:
        try:
            gateway.fetch("https://source.example/")
        except NetworkTimeoutError as error:
            failures.append(error.code)

    worker = threading.Thread(target=fetch)
    worker.start()
    try:
        assert entered.wait(1)
        with pytest.raises(NetworkTimeoutError, match="concurrency"):
            gateway.fetch("https://source.example/")
    finally:
        release.set()
        worker.join(1)
    assert failures == ["network_timeout"]


@pytest.mark.parametrize(
    "origin",
    [
        "http://source.example",
        "https://source.example/",
        "https://source.example?q=1",
        "https://user:secret@source.example",
        "https://source.example:8443",
    ],
)
def test_credentials_require_exact_https_origin(origin: str) -> None:
    with pytest.raises(ValueError):
        OriginCredentials(origin)


def test_credential_configuration_is_copied_and_header_injection_is_rejected() -> None:
    headers = {"api-key": SecretStr("synthetic-sensitive-value")}
    credentials = OriginCredentials("https://source.example", headers)
    headers["Host"] = SecretStr("evil.example")
    assert "Host" not in credentials.headers
    with pytest.raises(ValueError):
        OriginCredentials("https://source.example", {"api-key": SecretStr("secret\r\nHost: evil")})


@pytest.mark.parametrize("seconds", [0, -1, float("inf"), float("nan"), 121, True])
def test_timeout_settings_are_strictly_bounded(seconds: float) -> None:
    with pytest.raises(ValueError):
        NetworkPolicy(("source.example",), total_timeout_seconds=seconds)


@pytest.mark.parametrize("concurrency", [0, -1, 17, True, 1.5])
def test_request_concurrency_settings_are_strictly_bounded(concurrency: int) -> None:
    with pytest.raises(ValueError):
        create_network_gateway(
            NetworkPolicy(("source.example",)), max_concurrent_requests=concurrency
        )


@pytest.mark.parametrize("phase", ["headers", "body"])
def test_total_deadline_interrupts_blocking_headers_and_closed_connection_body(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    sockets, _queries = _install_socket_fixtures(
        monkeypatch, [_response(headers=b"Connection: close\r\n")]
    )
    shutdown = threading.Event()
    original_shutdown = FixtureSocket.shutdown

    def signal_shutdown(connection: FixtureSocket, how: int) -> None:
        original_shutdown(connection, how)
        shutdown.set()

    def stalled(*args: object, **kwargs: object) -> None:
        assert shutdown.wait(1), "deadline did not interrupt active socket"
        raise OSError("synthetic-sensitive-value")

    monkeypatch.setattr(FixtureSocket, "shutdown", signal_shutdown)
    if phase == "headers":
        original_getresponse = http.client.HTTPConnection.getresponse

        def stalled_headers(connection: http.client.HTTPConnection) -> None:
            original_getresponse(connection)
            stalled()

        monkeypatch.setattr(http.client.HTTPConnection, "getresponse", stalled_headers)
    else:
        monkeypatch.setattr(http.client.HTTPResponse, "read", stalled)
    gateway = create_network_gateway(NetworkPolicy(("source.example",), total_timeout_seconds=0.05))
    started = time.monotonic()
    with pytest.raises(NetworkTimeoutError) as captured:
        gateway.fetch("https://source.example/")
    assert "synthetic-sensitive-value" not in "".join(traceback.format_exception(captured.value))
    assert time.monotonic() - started < 1
    assert sockets[0].shutdown_called and sockets[0].closed


@pytest.mark.parametrize(
    "headers",
    [
        b"Content-Type: application/json\r\n",
        b"Content-Length: 9999\r\n",
        b"Transfer-Encoding: chunked\r\n",
    ],
)
def test_ambiguous_response_headers_close_transport(
    monkeypatch: pytest.MonkeyPatch,
    headers: bytes,
) -> None:
    sockets, _queries = _install_socket_fixtures(monkeypatch, [_response(headers=headers)])
    with pytest.raises(NetworkRequestError):
        create_network_gateway(NetworkPolicy(("source.example",))).fetch("https://source.example/")
    assert sockets[0].closed


@pytest.mark.parametrize("second_name", [b"Link", b"link", b"LINK"])
def test_duplicate_pagination_links_are_rejected_before_dictionary_conversion(
    monkeypatch: pytest.MonkeyPatch,
    second_name: bytes,
) -> None:
    headers = (
        b'Link: <https://source.example/first>; rel="next"\r\n'
        + second_name
        + b': <https://source.example/second>; rel="next"\r\n'
    )
    sockets, _queries = _install_socket_fixtures(monkeypatch, [_response(headers=headers)])
    with pytest.raises(NetworkRequestError, match="ambiguous duplicate response headers"):
        create_network_gateway(NetworkPolicy(("source.example",))).fetch("https://source.example/")
    assert sockets[0].closed


def test_truncated_response_is_failure_and_closes_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets, _queries = _install_socket_fixtures(
        monkeypatch,
        [
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 100\r\n\r\nshort",
        ],
    )
    with pytest.raises(NetworkRequestError, match="truncated"):
        create_network_gateway(NetworkPolicy(("source.example",))).fetch("https://source.example/")
    assert sockets[0].closed


def test_real_redirect_rejects_private_dns_and_closes_prior_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets, queries = _install_socket_fixtures(
        monkeypatch,
        [
            _response(302, b"Location: /second\r\n", b""),
        ],
    )
    with pytest.raises(NetworkPolicyViolation, match="private"):
        create_network_gateway(NetworkPolicy(("source.example",))).fetch("https://source.example/")
    assert queries == ["source.example", "source.example"]
    assert len(sockets) == 1
    assert sockets[0].closed


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_untyped_empty_http_error_retains_status_and_retry_metadata(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    sockets, _ = _install_socket_fixtures(
        monkeypatch,
        [f"HTTP/1.1 {status} Error\r\nRetry-After: 8\r\nContent-Length: 0\r\n\r\n".encode()],
    )
    result = create_network_gateway(NetworkPolicy(("source.example",))).fetch(
        "https://source.example/"
    )
    assert result.status_code == status
    assert result.body == b""
    assert result.redacted_headers["Retry-After"] == "8"
    assert len(sockets) == 1 and sockets[0].closed


@pytest.mark.parametrize("query", ["api-key=fixture-key", "renamed=wrapped-fixture-key"])
@pytest.mark.parametrize("scheme", ["Bearer ", "bearer ", "bEaReR ", "bEaReR   "])
@pytest.mark.parametrize("include_query_credential", [False, True])
def test_cross_origin_location_cannot_forward_reflected_query_credentials(
    monkeypatch: pytest.MonkeyPatch, query: str, scheme: str, include_query_credential: bool
) -> None:
    sockets, _ = _install_socket_fixtures(
        monkeypatch,
        [
            _response(
                302, f"Location: https://other.example/next?{query}&visible=1\r\n".encode(), b""
            ),
            _response(),
        ],
    )
    credentials = OriginCredentials(
        "https://source.example",
        {"Authorization": SecretStr(scheme + "fixture-key")},
        {"api-key": SecretStr("fixture-key")} if include_query_credential else {},
    )
    result = create_network_gateway(
        NetworkPolicy(("source.example", "other.example")), credentials
    ).fetch("https://source.example/start")
    sent = b"".join(sockets[1].sent)
    assert result.status_code == 200
    assert b"GET /next?visible=1 HTTP/1.1" in sent
    assert b"fixture-key" not in sent and b"Authorization:" not in sent
    assert all(connection.closed for connection in sockets)


@pytest.mark.parametrize("header", ["Retry-After", "X-RateLimit-Remaining", "X-RateLimit-Reset"])
@pytest.mark.parametrize("mixed_case", [False, True])
def test_duplicate_rate_headers_are_policy_blocked_before_values_can_be_lost(
    monkeypatch: pytest.MonkeyPatch,
    header: str,
    mixed_case: bool,
) -> None:
    second = header.lower() if mixed_case else header
    wire_headers = f"{header}: 9000\r\n{second}: 12\r\n".encode()
    sockets, _ = _install_socket_fixtures(
        monkeypatch, [_response(status=429, headers=wire_headers)]
    )
    with pytest.raises(NetworkPolicyViolation, match="ambiguous duplicate rate-limit headers"):
        fetch_with_policy(NetworkPolicy(("source.example",)), "https://source.example/document")
    assert len(sockets) == 1 and sockets[0].closed


@pytest.mark.parametrize("header_size", [65536, 65537])
def test_header_line_parser_limit_is_a_nonretryable_policy_boundary(
    monkeypatch: pytest.MonkeyPatch,
    header_size: int,
) -> None:
    headers = b"Retry-After: " + b"9" * header_size + b"\r\n"
    sockets, _ = _install_socket_fixtures(monkeypatch, [_response(status=429, headers=headers)])
    with pytest.raises(NetworkPolicyViolation, match="header parsing rejected"):
        fetch_with_policy(NetworkPolicy(("source.example",)), "https://source.example/document")
    assert len(sockets) == 1 and sockets[0].closed


def test_header_count_parser_limit_does_not_discard_late_rate_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = b"X-Padding: x\r\n" * 100 + b"Retry-After: 9000\r\n"
    sockets, _ = _install_socket_fixtures(monkeypatch, [_response(status=429, headers=headers)])
    with pytest.raises(NetworkPolicyViolation, match="header parsing rejected"):
        fetch_with_policy(NetworkPolicy(("source.example",)), "https://source.example/document")
    assert len(sockets) == 1 and sockets[0].closed


def test_peer_disconnect_before_headers_remains_a_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets, _ = _install_socket_fixtures(monkeypatch, [b""])
    with pytest.raises(NetworkRequestError, match="response disconnected"):
        fetch_with_policy(NetworkPolicy(("source.example",)), "https://source.example/document")
    assert len(sockets) == 1 and sockets[0].closed


@pytest.mark.parametrize("header", ["Location", "Content-Location", "X-Trace-Echo"])
@pytest.mark.parametrize(
    "value",
    [
        "review/synthetic+credential==",
        "review%2Fsynthetic%2Bcredential%3D%3D",
        "review%2fsynthetic%2bcredential%3d%3d",
    ],
)
def test_known_secret_response_metadata_is_redacted_before_and_after_url_decoding(
    monkeypatch: pytest.MonkeyPatch, header: str, value: str
) -> None:
    sockets, _ = _install_socket_fixtures(
        monkeypatch,
        [_response(headers=f"{header}: https://source.example/?renamed={value}\r\n".encode())],
    )
    credentials = OriginCredentials(
        "https://source.example", {"api-key": SecretStr("review/synthetic+credential==")}
    )
    result = create_network_gateway(NetworkPolicy(("source.example",)), credentials).fetch(
        "https://source.example/"
    )
    assert result.redacted_headers[header] == "REDACTED"
    assert result.body == b"document"
    assert all(connection.closed for connection in sockets)
