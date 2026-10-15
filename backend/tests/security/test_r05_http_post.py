"""实际http.client序列化的隔离socket负例，不计模型live。"""

import hashlib

import pytest
from pydantic import SecretStr
from test_r03_network_transport import _install_socket_fixtures, _response

from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    OriginCredentials,
    create_network_gateway,
)


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
def test_post_preserves_exact_json_tls_origin_and_protocol_credentials(monkeypatch, protocol):
    sockets, queries = _install_socket_fixtures(monkeypatch, [_response()])
    payload = '{"model":"chosen-model","messages":[{"role":"user","content":"公开资料"}]}'.encode()
    secret = "synthetic-provider-key"
    credentials = OriginCredentials(
        "https://source.example",
        {"Authorization": SecretStr("Bearer " + secret)}
        if protocol == "openai"
        else {"x-api-key": SecretStr(secret)},
    )
    gateway = create_network_gateway(NetworkPolicy(("source.example",)), credentials)
    result = gateway.post_json(
        "https://source.example/v1/messages"
        if protocol == "anthropic"
        else "https://source.example/chat/completions",
        payload,
        protocol_headers={"anthropic-version": "2023-06-01"} if protocol == "anthropic" else {},
    )
    sent = b"".join(sockets[0].sent)
    header, body = sent.split(b"\r\n\r\n", 1)
    assert header.startswith(b"POST /")
    assert b"Host: source.example\r\n" in header
    assert b"Content-Type: application/json" in header
    assert body == payload
    assert f"Content-Length: {len(payload)}".encode() in header
    assert (b"anthropic-version: 2023-06-01" in header) is (protocol == "anthropic")
    assert secret.encode() in header
    assert (
        result.request_fingerprint_sha256 == hashlib.sha256(result.final_url.encode()).hexdigest()
    )
    assert queries == ["source.example"]
    assert sockets[0].sni == "source.example" and sockets[0].closed


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_post_redirect_is_rejected_without_forwarding_body_or_credentials(monkeypatch, status):
    sockets, queries = _install_socket_fixtures(
        monkeypatch, [_response(status, b"Location: https://other.example/receive\r\n", b"")]
    )
    gateway = create_network_gateway(NetworkPolicy(("source.example", "other.example")))
    with pytest.raises(NetworkPolicyViolation, match="redirect hop limit"):
        gateway.post_json("https://source.example/", b'{"private":"isolated-synthetic"}')
    assert len(sockets) == 1 and sockets[0].closed
    assert queries == ["source.example"]


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500, 503])
def test_post_http_errors_are_not_retried_or_replaced_by_an_empty_success(monkeypatch, status):
    sockets, _ = _install_socket_fixtures(monkeypatch, [_response(status)])
    result = create_network_gateway(NetworkPolicy(("source.example",))).post_json(
        "https://source.example/", b"{}"
    )
    assert result.status_code == status and result.body == b""
    assert len(sockets) == 1 and sockets[0].closed


@pytest.mark.parametrize(
    "payload",
    [b"", b"x" * (1048576 + 1), "not-bytes"],
    ids=["empty", "oversized", "not_bytes"],
)
def test_invalid_post_body_fails_before_dns(monkeypatch, payload):
    sockets, queries = _install_socket_fixtures(monkeypatch, [])
    gateway = create_network_gateway(NetworkPolicy(("source.example",)))
    with pytest.raises(ValueError, match="body"):
        gateway.post_json("https://source.example/", payload)
    assert sockets == queries == []


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "other.example"},
        {"Authorization": "new-secret"},
        {"anthropic-version": "2023-06-01\r\nInjected: yes"},
        {"Content-Length": "0"},
    ],
)
def test_caller_cannot_inject_transport_or_authentication_headers(monkeypatch, headers):
    sockets, queries = _install_socket_fixtures(monkeypatch, [])
    with pytest.raises(ValueError, match="protocol header"):
        create_network_gateway(NetworkPolicy(("source.example",))).post_json(
            "https://source.example/", b"{}", protocol_headers=headers
        )
    assert sockets == queries == []
