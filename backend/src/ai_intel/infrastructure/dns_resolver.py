"""显式配置的标准DoH解析复用同一个有界HTTPS网关，不放宽公网IP限制。"""

import time
from base64 import urlsafe_b64encode

import dns.exception
import dns.flags
import dns.message
import dns.rcode
import dns.rdatatype

from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkResolutionError,
    RequestDeadline,
    create_network_gateway,
    is_private_or_local,
)


class CloudflareDohResolver:
    """仅可信部署配置可选；固定公共解析器、验证CA、wireformat且不使用系统代理。"""

    def __call__(self, hostname: str, deadline: RequestDeadline) -> list[str]:
        deadline = RequestDeadline(min(deadline.expires_at, time.monotonic() + 5))
        resolver = create_network_gateway(
            NetworkPolicy(
                allowed_domains=("1.1.1.1",),
                allowed_content_types=("application/dns-message",),
                max_response_bytes=65535,
                total_timeout_seconds=min(5, deadline.remaining_seconds()),
                dns_resolver="system",
            )
        )
        addresses: list[str] = []
        for record_type in (dns.rdatatype.A, dns.rdatatype.AAAA):
            query = dns.message.make_query(hostname, record_type)
            encoded = urlsafe_b64encode(query.to_wire()).rstrip(b"=").decode("ascii")
            deadline.remaining_seconds()
            result = resolver.fetch("https://1.1.1.1/dns-query?dns=" + encoded, deadline=deadline)
            if result.status_code != 200:
                raise NetworkResolutionError("configured DNS resolver request failed")
            try:
                response = dns.message.from_wire(result.body, raise_on_truncation=True)
                if (
                    not isinstance(response, dns.message.QueryMessage)
                    or response.flags & dns.flags.TC
                    or not query.is_response(response)
                    or response.rcode() != dns.rcode.NOERROR
                ):
                    raise dns.exception.FormError
                chain = response.resolve_chaining()
                if chain.answer is None and any(
                    rrset.rdtype in (dns.rdatatype.A, dns.rdatatype.AAAA)
                    for rrset in response.answer
                ):
                    raise dns.exception.FormError
                for rrset in response.answer:
                    if rrset.rdtype == dns.rdatatype.CNAME and len(rrset) != 1:
                        raise dns.exception.FormError
                    if rrset.rdtype in (dns.rdatatype.A, dns.rdatatype.AAAA):
                        if rrset.name != chain.canonical_name:
                            raise dns.exception.FormError
                        if any(is_private_or_local(record.to_text()) for record in rrset):
                            raise NetworkPolicyViolation(
                                "configured DNS answer is not a public set"
                            )
                if chain.answer is not None:
                    addresses.extend(record.to_text() for record in chain.answer)
            except dns.exception.DNSException:
                raise NetworkResolutionError("configured DNS resolver response invalid") from None
            if len(addresses) > 16:
                raise NetworkPolicyViolation("configured DNS answer exceeds address limit")
        deadline.remaining_seconds()
        if not addresses:
            raise NetworkResolutionError("configured DNS resolver returned no address")
        return list(dict.fromkeys(addresses))
