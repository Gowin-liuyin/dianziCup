"""独立审查发现的DNS/跨源秘密/状态和共享截止时间回归，fixture不计live。"""

from __future__ import annotations

import time
from base64 import urlsafe_b64decode
from urllib.parse import parse_qs, urlsplit

import dns.flags
import dns.message
import dns.rdatatype
import dns.rrset
import pytest

from ai_intel.infrastructure import dns_resolver
from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkResolutionError,
    NetworkTimeoutError,
    RequestDeadline,
    create_network_gateway,
)


@pytest.mark.parametrize(
    "mode", ["cname", "mixed_private_aaaa", "unrelated_owner", "cname_loop", "truncated"]
)
def test_both_address_families_and_only_valid_answer_chains(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    questions: list[int] = []

    class ResolverFixture:
        def fetch(self, url: str, *, deadline: RequestDeadline) -> FetchResult:
            deadline.remaining_seconds()
            encoded = parse_qs(urlsplit(url).query)["dns"][0]
            query = dns.message.from_wire(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            record_type = query.question[0].rdtype
            questions.append(record_type)
            response = dns.message.make_response(query)
            if mode == "cname":
                response.answer.append(
                    dns.rrset.from_text("source.example.", 60, "IN", "CNAME", "alias.example.")
                )
                if record_type == dns.rdatatype.A:
                    response.answer.append(
                        dns.rrset.from_text("alias.example.", 60, "IN", "A", "93.184.216.34")
                    )
            elif mode == "mixed_private_aaaa":
                response.answer.append(
                    dns.rrset.from_text("source.example.", 60, "IN", "A", "93.184.216.34")
                    if record_type == dns.rdatatype.A
                    else dns.rrset.from_text("source.example.", 60, "IN", "AAAA", "::1")
                )
            elif mode == "unrelated_owner":
                response.answer.append(
                    dns.rrset.from_text("unrelated.example.", 60, "IN", "A", "93.184.216.34")
                )
            elif mode == "cname_loop":
                response.answer.extend(
                    [
                        dns.rrset.from_text("source.example.", 60, "IN", "CNAME", "alias.example."),
                        dns.rrset.from_text("alias.example.", 60, "IN", "CNAME", "source.example."),
                    ]
                )
            else:
                response.flags |= dns.flags.TC
                response.answer.append(
                    dns.rrset.from_text("source.example.", 60, "IN", "A", "93.184.216.34")
                )
            return FetchResult(url, 200, "application/dns-message", response.to_wire())

    monkeypatch.setattr(dns_resolver, "create_network_gateway", lambda policy: ResolverFixture())
    if mode == "cname":
        assert dns_resolver.CloudflareDohResolver()(
            "source.example", RequestDeadline(time.monotonic() + 1)
        ) == ["93.184.216.34"]
        assert questions == [dns.rdatatype.A, dns.rdatatype.AAAA]
    else:
        with pytest.raises(
            NetworkPolicyViolation if mode == "mixed_private_aaaa" else NetworkResolutionError
        ):
            dns_resolver.CloudflareDohResolver()(
                "source.example", RequestDeadline(time.monotonic() + 1)
            )
        if mode == "mixed_private_aaaa":
            assert questions == [dns.rdatatype.A, dns.rdatatype.AAAA]


def test_doh_never_refreshes_an_expired_parent_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    def delayed_factory(policy: NetworkPolicy):
        time.sleep(0.06)
        gateway = create_network_gateway(policy)

        def request(url, addresses, deadline, headers):
            requests.append(url)
            raise AssertionError("network must not start after the outer deadline")

        monkeypatch.setattr(gateway._transport, "request", request)
        return gateway

    monkeypatch.setattr(dns_resolver, "create_network_gateway", delayed_factory)
    with pytest.raises(NetworkTimeoutError):
        dns_resolver.CloudflareDohResolver()(
            "source.example", RequestDeadline(time.monotonic() + 0.03)
        )
    assert requests == []
