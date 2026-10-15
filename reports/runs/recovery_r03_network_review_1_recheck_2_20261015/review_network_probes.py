"""独立审查探针；全部失败分支用合成输入，不调用外网或读取凭据。"""

from __future__ import annotations

import io
import json
import socket
import ssl
import time
from base64 import urlsafe_b64decode
from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import dns.flags
import dns.message
import dns.rdatatype
import dns.rrset
from pydantic import SecretStr

from ai_intel.infrastructure import dns_resolver, http_transport
from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkPolicy,
    OriginCredentials,
    RequestDeadline,
    create_network_gateway,
)


def dns_probe(mode: str) -> dict[str, object]:
    calls: list[str] = []

    class ResolverFixture:
        def fetch(self, url: str, *, deadline: RequestDeadline) -> FetchResult:
            deadline.remaining_seconds()
            encoded = parse_qs(urlsplit(url).query)["dns"][0]
            question = dns.message.from_wire(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            record_type = question.question[0].rdtype
            calls.append(dns.rdatatype.to_text(record_type))
            response = dns.message.make_response(question)
            if mode == "mixed_a_aaaa":
                response.answer.append(
                    dns.rrset.from_text("registered.example.", 60, "IN", "A", "93.184.216.34")
                    if record_type == dns.rdatatype.A
                    else dns.rrset.from_text("registered.example.", 60, "IN", "AAAA", "::1")
                )
            elif mode == "unrelated_owner":
                response.answer.append(
                    dns.rrset.from_text("unrelated.example.", 60, "IN", "A", "93.184.216.34")
                )
            elif mode == "loop_and_unrelated_owner":
                response.answer.extend([
                    dns.rrset.from_text("registered.example.", 60, "IN", "CNAME", "alias.example."),
                    dns.rrset.from_text("alias.example.", 60, "IN", "CNAME", "registered.example."),
                    dns.rrset.from_text("unrelated.example.", 60, "IN", "A", "93.184.216.34"),
                ])
            elif mode == "truncated_answer":
                response.flags |= dns.flags.TC
                response.answer.append(
                    dns.rrset.from_text("registered.example.", 60, "IN", "A", "93.184.216.34")
                )
            elif mode == "valid_cname":
                response.answer.append(
                    dns.rrset.from_text("registered.example.", 60, "IN", "CNAME", "alias.example.")
                )
                if record_type == dns.rdatatype.A:
                    response.answer.append(
                        dns.rrset.from_text("alias.example.", 60, "IN", "A", "93.184.216.34")
                    )
            else:
                raise AssertionError(mode)
            assert question.is_response(response)
            return FetchResult(url, 200, "application/dns-message", response.to_wire())

    outcome: dict[str, object] = {"mode": mode, "queries": calls, "fixture_only": True}
    with patch.object(dns_resolver, "create_network_gateway", lambda policy: ResolverFixture()):
        try:
            outcome["addresses_accepted"] = dns_resolver.CloudflareDohResolver()(
                "registered.example", RequestDeadline(time.monotonic() + 1)
            )
        except Exception as error:
            outcome["exception_type"] = type(error).__name__
            outcome["exception_code"] = getattr(error, "code", None)
    return outcome


class SocketFixture:
    def __init__(self, wire: bytes) -> None:
        self.wire = wire
        self.sent: list[bytes] = []
        self.connected: tuple[str, int] | None = None
        self.closed = False
        self.sni = ""

    def connect(self, target: tuple[str, int]) -> None:
        self.connected = target

    def getpeername(self) -> tuple[str, int]:
        return "93.184.216.34", 443

    def settimeout(self, timeout: float) -> None:
        pass

    def sendall(self, value: bytes) -> None:
        self.sent.append(value)

    def makefile(self, mode: str) -> io.BytesIO:
        return io.BytesIO(self.wire)

    def do_handshake(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def shutdown(self, how: int) -> None:
        pass


def http_probe(mode: str) -> dict[str, object]:
    sentinel = "review-synthetic-credential"
    wires = [
        (
            "HTTP/1.1 302 Found\r\n"
            f"Location: https://other.example/next?api-key={sentinel}&visible=1\r\n"
            "Content-Length: 0\r\n\r\n"
        ).encode(),
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nok",
    ]
    if mode == "cross_origin_lowercase_bearer":
        wires[0] = (
            "HTTP/1.1 302 Found\r\n"
            f"Location: https://other.example/next?renamed={sentinel}&visible=1\r\n"
            "Content-Length: 0\r\n\r\n"
        ).encode()
    elif mode != "cross_origin_location_query":
        status = 401 if mode == "401_missing_content_type" else 429
        wires = [f"HTTP/1.1 {status} Error\r\nContent-Length: 0\r\n\r\n".encode()]
    connections: list[SocketFixture] = []

    def new_socket(*args: object) -> SocketFixture:
        connection = SocketFixture(wires[len(connections)])
        connections.append(connection)
        return connection

    def wrap(context: ssl.SSLContext, connection: SocketFixture, **options: object) -> SocketFixture:
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        connection.sni = str(options["server_hostname"])
        return connection

    records = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
    outcome: dict[str, object] = {"mode": mode, "fixture_only": True}
    with (
        patch.object(http_transport.socket, "socket", new_socket),
        patch.object(http_transport.socket, "getaddrinfo", lambda *args, **kwargs: records),
        patch.object(http_transport.ssl.SSLContext, "wrap_socket", wrap),
    ):
        gateway = create_network_gateway(
            NetworkPolicy(("registered.example", "other.example")),
            OriginCredentials(
                "https://registered.example",
                {"Authorization": SecretStr("bEaReR " + sentinel if mode == "cross_origin_lowercase_bearer" else sentinel)},
                {} if mode == "cross_origin_lowercase_bearer" else {"api-key": SecretStr(sentinel)},
            ),
        )
        try:
            result = gateway.fetch("https://registered.example/start")
            outcome["status_code"] = result.status_code
        except Exception as error:
            outcome["exception_type"] = type(error).__name__
            outcome["exception_code"] = getattr(error, "code", None)
            outcome["exception_retains_status"] = getattr(error, "status_code", None)
    outcome["connections_closed"] = all(connection.closed for connection in connections)
    if len(connections) == 2:
        sent = b"".join(connections[1].sent)
        outcome["cross_origin_query_contains_injected_secret"] = sentinel.encode() in sent
        outcome["cross_origin_authorization_header_present"] = b"Authorization:" in sent
        outcome["cross_origin_host"] = connections[1].sni
    return outcome


def deadline_probe() -> dict[str, object]:
    factories: list[dict[str, float]] = []
    total_budget = 0.05
    started = time.monotonic()
    outer_deadline = RequestDeadline(started + total_budget)

    def delayed_factory(policy: NetworkPolicy) -> object:
        factories.append({"requested_inner_budget": policy.total_timeout_seconds})
        time.sleep(0.08)
        gateway = create_network_gateway(policy)

        def request(url: str, addresses: tuple[str, ...], deadline: RequestDeadline, headers: object):
            factories[-1]["network_started_after_seconds"] = time.monotonic() - started
            factories[-1]["inner_remaining_after_outer_expired"] = deadline.remaining_seconds()
            time.sleep(0.03)

            class Response:
                status_code = 200
                headers = {"Content-Type": "application/dns-message"}

                def iter_bytes(self):
                    encoded = parse_qs(urlsplit(url).query)["dns"][0]
                    query = dns.message.from_wire(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                    response = dns.message.make_response(query)
                    response.answer.append(dns.rrset.from_text("registered.example.", 60, "IN", "A", "93.184.216.34"))
                    yield response.to_wire()

                def close(self):
                    pass

            return Response()

        gateway._transport.request = request
        gateway._transport.resolve_addresses = lambda hostname, deadline: ["1.1.1.1"]
        return gateway

    result: dict[str, object] = {"mode": "nested_doh_deadline", "fixture_only": True}
    with patch.object(dns_resolver, "create_network_gateway", delayed_factory):
        try:
            dns_resolver.CloudflareDohResolver()("registered.example", outer_deadline)
            result["completed"] = True
        except Exception as error:
            result["exception_type"] = type(error).__name__
            result["exception_code"] = getattr(error, "code", None)
    result["budget_seconds"] = total_budget
    result["elapsed_seconds"] = time.monotonic() - started
    result["factory_receipts"] = factories
    return result


if __name__ == "__main__":
    print(json.dumps({
        "observed_at": datetime.now().astimezone().isoformat(),
        "note": "probe execution result; exit 0 means the probe ran, not that negative cases passed",
        "dns": [dns_probe(mode) for mode in (
            "valid_cname", "mixed_a_aaaa", "unrelated_owner", "loop_and_unrelated_owner", "truncated_answer",
        )],
        "http": [http_probe(mode) for mode in (
            "cross_origin_location_query", "401_missing_content_type", "429_missing_content_type", "cross_origin_lowercase_bearer",
        )],
        "deadline": deadline_probe(),
    }, ensure_ascii=False, indent=2))
