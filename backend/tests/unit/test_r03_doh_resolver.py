"""显式DoH的wireformat/身份/大小/公网边界；fixture不计真实解析。"""

import time
from base64 import urlsafe_b64decode
from urllib.parse import parse_qs, urlsplit

import dns.message
import dns.rcode
import dns.rrset
import pytest

from ai_intel.infrastructure.dns_resolver import CloudflareDohResolver
from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkResolutionError,
    RequestDeadline,
)


@pytest.mark.parametrize(
    "mode",
    ["public", "ipv6", "private", "empty", "nxdomain", "mismatch", "malformed", "http_failed"],
)
def test_explicit_doh_keeps_wire_response_and_address_boundaries(monkeypatch, mode):
    calls = []

    class FixtureResolverGateway:
        def fetch(self, url):
            encoded = parse_qs(urlsplit(url).query)["dns"][0]
            question = dns.message.from_wire(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            response = dns.message.make_response(question)
            if mode == "nxdomain":
                response.set_rcode(dns.rcode.NXDOMAIN)
            elif mode == "mismatch":
                response.id ^= 1
            elif mode != "empty" and (mode != "ipv6" or question.question[0].rdtype == 28):
                address = "10.0.0.1" if mode == "private" else "1.1.1.2"
                record_type = "AAAA" if mode == "ipv6" else "A"
                if record_type == "AAAA":
                    address = "2606:4700:4700::1111"
                response.answer.append(
                    dns.rrset.from_text("example.com.", 60, "IN", record_type, address)
                )
            return FetchResult(
                final_url=url,
                status_code=403 if mode == "http_failed" else 200,
                content_type="application/dns-message",
                body=b"broken" if mode == "malformed" else response.to_wire(),
            )

    def fixture_gateway(policy):
        calls.append(policy)
        assert policy.allowed_domains == ("1.1.1.1",)
        assert policy.max_response_bytes == 65535
        assert policy.dns_resolver == "system"
        assert policy.allowed_schemes == ("https",)
        return FixtureResolverGateway()

    monkeypatch.setattr(
        "ai_intel.infrastructure.dns_resolver.create_network_gateway", fixture_gateway
    )
    deadline = RequestDeadline(time.monotonic() + 2)
    if mode in ("public", "ipv6"):
        addresses = CloudflareDohResolver()("example.com", deadline)
        assert addresses == (["1.1.1.2"] if mode == "public" else ["2606:4700:4700::1111"])
    elif mode == "private":
        with pytest.raises(NetworkPolicyViolation):
            CloudflareDohResolver()("example.com", deadline)
    else:
        with pytest.raises(NetworkResolutionError):
            CloudflareDohResolver()("example.com", deadline)
    assert len(calls) <= 2


def test_unknown_resolver_mode_is_rejected_instead_of_falling_back():
    with pytest.raises(ValueError, match="dns_resolver"):
        NetworkPolicy(allowed_domains=("example.com",), dns_resolver="unapproved_resolver")
