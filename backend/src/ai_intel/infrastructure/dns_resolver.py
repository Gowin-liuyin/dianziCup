"""显式配置的标准DoH解析复用同一个有界HTTPS网关，不放宽公网IP限制。"""

from base64 import urlsafe_b64encode

import dns.exception
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
        for record_type in (dns.rdatatype.A, dns.rdatatype.AAAA):
            query = dns.message.make_query(hostname, record_type)
            encoded = urlsafe_b64encode(query.to_wire()).rstrip(b"=").decode("ascii")
            resolver = create_network_gateway(
                NetworkPolicy(
                    allowed_domains=("1.1.1.1",),
                    allowed_content_types=("application/dns-message",),
                    max_response_bytes=65535,
                    total_timeout_seconds=min(5, deadline.remaining_seconds()),
                    dns_resolver="system",
                )
            )
            result = resolver.fetch("https://1.1.1.1/dns-query?dns=" + encoded)
            if result.status_code != 200:
                raise NetworkResolutionError("configured DNS resolver request failed")
            try:
                response = dns.message.from_wire(result.body)
            except dns.exception.DNSException:
                raise NetworkResolutionError("configured DNS resolver response invalid") from None
            if not query.is_response(response) or response.rcode() != dns.rcode.NOERROR:
                raise NetworkResolutionError("configured DNS resolver returned no valid answer")
            addresses = [
                record.to_text()
                for rrset in response.answer
                if rrset.rdtype == record_type
                for record in rrset
            ]
            if addresses:
                if len(addresses) > 16 or any(
                    is_private_or_local(address) for address in addresses
                ):
                    raise NetworkPolicyViolation(
                        "configured DNS answer is not a bounded public set"
                    )
                deadline.remaining_seconds()
                return list(dict.fromkeys(addresses))
        raise NetworkResolutionError("configured DNS resolver returned no address")
