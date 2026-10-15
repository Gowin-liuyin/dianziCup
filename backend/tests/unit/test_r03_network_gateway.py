"""R03 gateway behavior uses isolated, explicitly injected response fixtures."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import pytest

from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
    fetch_with_policy,
)


@dataclass
class FixtureResponse:
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=lambda: {"Content-Type": "text/plain"})
    chunks: list[bytes] = field(default_factory=lambda: [b"document"])
    closed: bool = False
    reads: int = 0

    def iter_bytes(self) -> Iterable[bytes]:
        for chunk in self.chunks:
            self.reads += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


POLICY = NetworkPolicy(allowed_domains=("source.example",))


def test_normal_response_and_relative_redirect_are_closed() -> None:
    redirect = FixtureResponse(302, {"Location": "../final?api-key=fixture-secret"})
    document = FixtureResponse()
    fetched: list[str] = []

    def transport(url: str) -> FixtureResponse:
        fetched.append(url)
        return redirect if len(fetched) == 1 else document

    result = fetch_with_policy(
        POLICY, "https://source.example/dir/start", transport, lambda host: ["93.184.216.34"]
    )
    assert fetched == [
        "https://source.example/dir/start",
        "https://source.example/final?api-key=fixture-secret",
    ]
    assert result.body == b"document"
    assert result.content_type == "text/plain"
    assert "fixture-secret" not in result.final_url
    assert redirect.closed and document.closed


@pytest.mark.parametrize("addresses", [[], ["10.0.0.1"], ["93.184.216.34", "127.0.0.1"]])
def test_invalid_dns_cannot_reach_fixture_transport(addresses: list[str]) -> None:
    calls: list[str] = []

    def transport(url: str) -> FixtureResponse:
        calls.append(url)
        return FixtureResponse()

    with pytest.raises(NetworkPolicyViolation):
        fetch_with_policy(POLICY, "https://source.example/", transport, lambda host: addresses)
    assert calls == []


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_error_status_is_returned_once_and_response_is_closed(status: int) -> None:
    response = FixtureResponse(status)
    result = fetch_with_policy(
        POLICY, "https://source.example/", lambda url: response, lambda host: ["93.184.216.34"]
    )
    assert result.status_code == status
    assert response.reads == 0
    assert result.body == b""
    assert response.closed


@pytest.mark.parametrize(
    ("headers", "chunks", "expected_error"),
    [
        ({"Content-Type": "application/jsonp"}, [b"{}"], UnsupportedContentTypeError),
        ({}, [b"missing type"], UnsupportedContentTypeError),
        ({"Content-Type": "text/plain", "Content-Length": "100"}, [b"x"], ResponseTooLargeError),
        ({"Content-Type": "text/plain"}, [b"01234567890", b"never"], ResponseTooLargeError),
    ],
)
def test_rejected_response_is_closed_before_buffering_remainder(
    headers: dict[str, str], chunks: list[bytes], expected_error: type[Exception]
) -> None:
    response = FixtureResponse(headers=headers, chunks=chunks)
    policy = NetworkPolicy(allowed_domains=("source.example",), max_response_bytes=10)
    with pytest.raises(expected_error):
        fetch_with_policy(
            policy, "https://source.example/", lambda url: response, lambda host: ["93.184.216.34"]
        )
    assert response.closed
    assert response.reads <= 1


def test_redirect_to_private_dns_is_rechecked_and_closed() -> None:
    redirect = FixtureResponse(302, {"Location": "https://other.example/private"})
    policy = NetworkPolicy(allowed_domains=("source.example", "other.example"))
    calls: list[str] = []

    def transport(url: str) -> FixtureResponse:
        calls.append(url)
        return redirect

    with pytest.raises(NetworkPolicyViolation, match="private"):
        fetch_with_policy(
            policy,
            "https://source.example/",
            transport,
            lambda host: ["93.184.216.34"] if host == "source.example" else ["127.0.0.1"],
        )
    assert calls == ["https://source.example/"]
    assert redirect.closed


def test_fixture_transport_and_resolver_must_be_given_together() -> None:
    with pytest.raises(ValueError, match="together"):
        fetch_with_policy(POLICY, "https://source.example/", lambda url: FixtureResponse())
