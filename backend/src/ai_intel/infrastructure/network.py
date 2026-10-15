"""Bounded source fetching with per-hop policy checks and redacted audit metadata."""

from __future__ import annotations

import hashlib
import ipaddress
import math
import re
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Protocol
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

from pydantic import SecretStr

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECT_HOPS = 5
HOSTNAME_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
)
SENSITIVE_QUERY_KEYS = {
    "token",
    "access_token",
    "key",
    "api_key",
    "api-key",
    "apikey",
    "secret",
    "password",
    "sig",
    "signature",
    "x-quaketoken",
    "x-api-key",
    "authorization",
    "cookie",
}
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "api_key",
    "apikey",
    "x-quaketoken",
}


class NetworkPolicyViolation(PermissionError):
    """A request violates its registered network boundary."""

    code = "network_policy_violation"


class NetworkRequestError(RuntimeError):
    """A transport failure with a safe, fixed code for the task retry layer."""

    code = "network_error"


class NetworkResolutionError(NetworkRequestError):
    """DNS failed without exposing the resolver's raw diagnostic."""

    code = "network_dns_error"


class NetworkTlsError(NetworkRequestError):
    """The HTTPS certificate or hostname failed verification; do not relax validation."""

    code = "network_tls_error"


class NetworkTimeoutError(NetworkRequestError):
    """The total request budget expired, including wait, DNS and redirects."""

    code = "network_timeout"


class ResponseTooLargeError(NetworkRequestError):
    """Response reading stopped at the configured byte boundary."""

    code = "response_too_large"


class UnsupportedContentTypeError(NetworkRequestError):
    """The response's exact media type or encoding is unsupported."""

    code = "unsupported_content_type"


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    redacted_headers: dict[str, str] = field(default_factory=dict)
    request_fingerprint_sha256: str = ""


class TransportResponse(Protocol):
    status_code: int
    headers: dict[str, str]

    def iter_bytes(self) -> Iterable[bytes]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class RequestDeadline:
    expires_at: float

    def remaining_seconds(self) -> float:
        remaining = self.expires_at - time.monotonic()
        if remaining <= 0:
            raise NetworkTimeoutError("request total time limit exceeded") from None
        return remaining


def is_private_or_local(address: str) -> bool:
    """Only globally routable unicast addresses may reach the connector."""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True
    return not parsed.is_global or parsed.is_multicast or "%" in address


def redact_url(url: str) -> tuple[str, str]:
    """Remove URL credentials while keeping a fingerprint of the original request."""
    parts = urlsplit(url)
    pairs = [
        (key, "REDACTED" if key.lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    netloc = parts.netloc.rsplit("@", 1)[-1]
    redacted = urlunsplit((parts.scheme, netloc, parts.path, urlencode(pairs), ""))
    return redacted, hashlib.sha256(url.encode("utf-8")).hexdigest()


def redact_headers(
    headers: dict[str, str], sensitive_values: tuple[str, ...] = ()
) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS or any(
            secret in unquote(value) for secret in sensitive_values
        ):
            redacted[key] = "REDACTED"
        elif key.lower() in {"location", "content-location"}:
            try:
                redacted[key] = redact_url(value)[0]
            except ValueError:
                redacted[key] = "REDACTED"
        else:
            redacted[key] = value
        for secret in sensitive_values:
            redacted[key] = redacted[key].replace(secret, "REDACTED")
    return redacted


def classify_http_failure(status_code: int) -> str:
    """Only the task layer may retry; the network gateway makes one attempt per hop."""
    if status_code == 429:
        return "rate_limited"
    if status_code in (401, 403):
        return "permanent_auth_error"
    if 400 <= status_code < 500:
        return "permanent_client_error"
    if status_code >= 500:
        return "transient_server_error"
    return "succeeded"


@dataclass(frozen=True)
class NetworkPolicy:
    allowed_domains: tuple[str, ...]
    max_response_bytes: int = MAX_RESPONSE_BYTES
    allowed_content_types: tuple[str, ...] = (
        "text/html",
        "application/json",
        "application/pdf",
        "text/plain",
    )
    total_timeout_seconds: float = 10.0
    dns_resolver: Literal["system", "cloudflare_doh"] = "system"
    allowed_schemes: tuple[str, ...] = ("https",)

    def __post_init__(self) -> None:
        if self.dns_resolver not in ("system", "cloudflare_doh"):
            raise ValueError("dns_resolver must be system or cloudflare_doh")
        if (
            not isinstance(self.allowed_domains, tuple)
            or not self.allowed_domains
            or any(
                not isinstance(domain, str)
                or len(domain) > 253
                or not HOSTNAME_PATTERN.fullmatch(domain)
                for domain in self.allowed_domains
            )
        ):
            raise ValueError("registered domains must be nonempty canonical hostnames")
        if (
            isinstance(self.max_response_bytes, bool)
            or not isinstance(self.max_response_bytes, int)
            or not 1 <= self.max_response_bytes <= 64 * 1024 * 1024
        ):
            raise ValueError("max_response_bytes must be between 1 and 67108864")
        if (
            isinstance(self.total_timeout_seconds, bool)
            or not isinstance(self.total_timeout_seconds, (int, float))
            or not math.isfinite(self.total_timeout_seconds)
            or not 0 < self.total_timeout_seconds <= 120
        ):
            raise ValueError("total_timeout_seconds must be finite and between 0 and 120")
        if (
            not isinstance(self.allowed_schemes, tuple)
            or not self.allowed_schemes
            or any(scheme not in ("https", "http") for scheme in self.allowed_schemes)
        ):
            raise ValueError("allowed_schemes must explicitly contain https or http")
        if (
            not isinstance(self.allowed_content_types, tuple)
            or not self.allowed_content_types
            or any(
                not isinstance(media_type, str)
                or "/" not in media_type
                or media_type != media_type.lower()
                or ";" in media_type
                for media_type in self.allowed_content_types
            )
        ):
            raise ValueError("allowed_content_types must contain exact lowercase media types")

    def ensure_url_allowed(self, url: str) -> None:
        if not isinstance(url, str):
            raise NetworkPolicyViolation("URL must be a string")
        if not url.isascii():
            raise NetworkPolicyViolation("URL must use ASCII or percent encoding")
        if any(ord(character) <= 32 or ord(character) == 127 for character in url):
            raise NetworkPolicyViolation("URL contains forbidden control characters")
        try:
            parts = urlsplit(url)
            hostname = parts.hostname or ""
            port = parts.port
        except ValueError:
            raise NetworkPolicyViolation("URL is malformed") from None
        if parts.scheme not in self.allowed_schemes:
            raise NetworkPolicyViolation("scheme not allowed")
        if parts.username is not None or parts.password is not None:
            raise NetworkPolicyViolation("URL userinfo is forbidden")
        if not HOSTNAME_PATTERN.fullmatch(hostname) or len(hostname) > 253:
            raise NetworkPolicyViolation("URL hostname is malformed")
        if port not in (None, 443 if parts.scheme == "https" else 80):
            raise NetworkPolicyViolation("nonstandard port is forbidden")
        if not any(
            hostname == allowed or hostname.endswith("." + allowed)
            for allowed in self.allowed_domains
        ):
            raise NetworkPolicyViolation("domain not in allowlist")

    def ensure_target_address_allowed(self, address: str) -> None:
        if is_private_or_local(address):
            raise NetworkPolicyViolation("resolved address is private or local (DNS rebinding)")


def _origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    return (
        parts.scheme,
        parts.hostname or "",
        parts.port or (443 if parts.scheme == "https" else 80),
    )


def _strip_redirect_secrets(url: str, sensitive_values: tuple[str, ...]) -> str:
    """跨origin不携带敏感query；路径反射凭据时拒绝而非向另一主机发送。"""
    parts = urlsplit(url)
    pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in SENSITIVE_QUERY_KEYS
        and not any(secret in value or secret in key for secret in sensitive_values)
    ]
    target = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))
    if any(secret in unquote(target) for secret in sensitive_values):
        raise NetworkPolicyViolation("cross-origin redirect reflects a credential")
    return target


@dataclass(frozen=True)
class OriginCredentials:
    """Trusted configuration injects secrets only into one exact HTTPS origin."""

    origin: str
    headers: Mapping[str, SecretStr] = field(default_factory=dict, repr=False)
    query_parameters: Mapping[str, SecretStr] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        try:
            parts = urlsplit(self.origin)
            valid = (
                parts.scheme == "https"
                and bool(parts.hostname)
                and parts.port in (None, 443)
                and parts.username is None
                and parts.password is None
                and not parts.path
                and not parts.query
                and not parts.fragment
                and not any(ord(c) <= 32 for c in self.origin)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("credentials require an exact HTTPS origin without URL components")
        for key, value in self.headers.items():
            if (
                key.lower() not in SENSITIVE_HEADERS - {"set-cookie", "proxy-authorization"}
                or not isinstance(value, SecretStr)
                or not value.get_secret_value().isascii()
                or any(ord(c) < 32 or ord(c) == 127 for c in value.get_secret_value())
            ):
                raise ValueError("invalid trusted credential header")
        if any(
            key.lower() not in SENSITIVE_QUERY_KEYS or not isinstance(value, SecretStr)
            for key, value in self.query_parameters.items()
        ):
            raise ValueError("invalid trusted credential query parameter")
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))
        object.__setattr__(self, "query_parameters", MappingProxyType(dict(self.query_parameters)))

    def inject(self, url: str) -> tuple[str, dict[str, str]]:
        if _origin(url) != _origin(self.origin):
            return url, {}
        parts = urlsplit(url)
        pairs = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in {name.lower() for name in self.query_parameters}
        ]
        pairs.extend(
            (key, value.get_secret_value()) for key, value in self.query_parameters.items()
        )
        request_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))
        return request_url, {key: value.get_secret_value() for key, value in self.headers.items()}


def _fetch(
    policy: NetworkPolicy,
    url: str,
    transport: Callable[[str, tuple[str, ...], RequestDeadline, dict[str, str]], TransportResponse],
    resolve_addresses: Callable[[str, RequestDeadline], list[str]],
    deadline: RequestDeadline,
    max_redirect_hops: int,
    credentials: OriginCredentials | None = None,
) -> FetchResult:
    if (
        isinstance(max_redirect_hops, bool)
        or not isinstance(max_redirect_hops, int)
        or not 0 <= max_redirect_hops <= MAX_REDIRECT_HOPS
    ):
        raise ValueError("max_redirect_hops must be between 0 and 5")
    current_url = url
    secret_values = {
        value
        for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True)
        if key.lower() in SENSITIVE_QUERY_KEYS and value
    }
    if credentials:
        secret_values.update(
            value.get_secret_value() for value in credentials.query_parameters.values()
        )
        for value in credentials.headers.values():
            header_value = value.get_secret_value()
            secret_values.add(header_value)
            scheme, separator, token = header_value.partition(" ")
            if separator and scheme.casefold() == "bearer":
                secret_values.add(token.lstrip(" "))
    sensitive_values = tuple(value for value in secret_values if value)
    for hop in range(max_redirect_hops + 1):
        deadline.remaining_seconds()
        policy.ensure_url_allowed(current_url)
        addresses = resolve_addresses(urlsplit(current_url).hostname or "", deadline)
        if not addresses:
            raise NetworkPolicyViolation("DNS returned no addresses")
        for address in addresses:
            policy.ensure_target_address_allowed(address)
        request_url, headers = credentials.inject(current_url) if credentials else (current_url, {})
        response = transport(request_url, tuple(addresses), deadline, headers)
        try:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            if response.status_code in (301, 302, 303, 307, 308):
                location = response_headers.get("location", "")
                if not location:
                    raise NetworkPolicyViolation("redirect without location header")
                if hop == max_redirect_hops:
                    raise NetworkPolicyViolation("redirect hop limit exceeded")
                try:
                    next_url = urljoin(current_url, location)
                    policy.ensure_url_allowed(next_url)
                except ValueError:
                    raise NetworkPolicyViolation("redirect URL is malformed") from None
                if _origin(current_url) != _origin(next_url):
                    next_url = _strip_redirect_secrets(next_url, sensitive_values)
                    credentials = None
                if _origin(current_url)[0] == "https" and _origin(next_url)[0] == "http":
                    raise NetworkPolicyViolation("HTTPS downgrade is forbidden")
                current_url = next_url
                continue
            content_type = response_headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if not 200 <= response.status_code < 300:
                redacted_url, fingerprint = redact_url(request_url)
                return FetchResult(
                    final_url=redacted_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    body=b"",
                    redacted_headers=redact_headers(response.headers, sensitive_values),
                    request_fingerprint_sha256=fingerprint,
                )
            if content_type not in policy.allowed_content_types:
                raise UnsupportedContentTypeError("unsupported or missing response content type")
            if response_headers.get("content-encoding", "identity").lower() not in ("", "identity"):
                raise UnsupportedContentTypeError("unsupported response content encoding")
            content_length = response_headers.get("content-length")
            if content_length is not None and "transfer-encoding" in response_headers:
                raise NetworkRequestError("conflicting response framing headers")
            if content_length is not None:
                if (
                    len(content_length) > 20
                    or not content_length.isascii()
                    or not content_length.isdecimal()
                ):
                    raise NetworkRequestError("invalid response content length")
                if int(content_length) > policy.max_response_bytes:
                    raise ResponseTooLargeError("response exceeded size limit")
            body = bytearray()
            for chunk in response.iter_bytes():
                deadline.remaining_seconds()
                if len(body) + len(chunk) > policy.max_response_bytes:
                    raise ResponseTooLargeError("response exceeded size limit")
                body.extend(chunk)
            if content_length is not None and len(body) != int(content_length):
                raise NetworkRequestError("response body is truncated")
            deadline.remaining_seconds()
            redacted_url, fingerprint = redact_url(request_url)
            return FetchResult(
                final_url=redacted_url,
                status_code=response.status_code,
                content_type=content_type,
                body=bytes(body),
                redacted_headers=redact_headers(response.headers, sensitive_values),
                request_fingerprint_sha256=fingerprint,
            )
        finally:
            response.close()
    raise NetworkPolicyViolation("redirect hop limit exceeded")


class NetworkGateway:
    """Reuse one gateway per worker to share its bounded DNS and request concurrency."""

    def __init__(
        self,
        policy: NetworkPolicy,
        credentials: OriginCredentials | None = None,
        max_concurrent_requests: int = 4,
    ) -> None:
        from ai_intel.infrastructure.http_transport import PinnedHttpTransport

        if (
            isinstance(max_concurrent_requests, bool)
            or not isinstance(max_concurrent_requests, int)
            or not 1 <= max_concurrent_requests <= 16
        ):
            raise ValueError("max_concurrent_requests must be between 1 and 16")
        if credentials:
            policy.ensure_url_allowed(credentials.origin)
        self._policy = policy
        self._credentials = credentials
        self._request_slots = threading.BoundedSemaphore(max_concurrent_requests)
        self._transport = PinnedHttpTransport(policy.max_response_bytes, max_concurrent_requests)
        self._resolve_addresses: Callable[[str, RequestDeadline], list[str]] | None = None
        if policy.dns_resolver == "cloudflare_doh":
            from ai_intel.infrastructure.dns_resolver import CloudflareDohResolver

            self._resolve_addresses = CloudflareDohResolver()

    def fetch(
        self,
        url: str,
        max_redirect_hops: int = MAX_REDIRECT_HOPS,
        *,
        deadline: RequestDeadline | None = None,
    ) -> FetchResult:
        return self._bounded_fetch(url, max_redirect_hops, deadline, self._transport.request)

    def post_json(
        self,
        url: str,
        payload: bytes,
        *,
        protocol_headers: Mapping[str, str] | None = None,
        deadline: RequestDeadline | None = None,
    ) -> FetchResult:
        """JSON POST共享IP/TLS/预算边界；禁止重定向或调用方覆盖身份与Host。"""
        if type(payload) is not bytes or not 1 <= len(payload) <= 1048576:
            raise ValueError("JSON request body must be bounded to 1 MiB")
        extra_headers = dict(protocol_headers or {})
        if any(
            key != "anthropic-version"
            or not isinstance(value, str)
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None
            for key, value in extra_headers.items()
        ):
            raise ValueError("unsupported protocol header")
        return self._bounded_fetch(
            url,
            0,
            deadline,
            lambda target, addresses, budget, credentials: self._transport.request(
                target,
                addresses,
                budget,
                {**credentials, "Content-Type": "application/json", **extra_headers},
                method="POST",
                body=payload,
            ),
        )

    def _bounded_fetch(
        self,
        url: str,
        max_redirect_hops: int,
        deadline: RequestDeadline | None,
        transport: Callable[
            [str, tuple[str, ...], RequestDeadline, dict[str, str]], TransportResponse
        ],
    ) -> FetchResult:
        expires_at = time.monotonic() + self._policy.total_timeout_seconds
        deadline = RequestDeadline(min(expires_at, deadline.expires_at) if deadline else expires_at)
        if not self._request_slots.acquire(timeout=deadline.remaining_seconds()):
            raise NetworkTimeoutError("request concurrency wait exceeded total time limit")
        try:
            return _fetch(
                self._policy,
                url,
                transport,
                self._resolve_addresses or self._transport.resolve_addresses,
                deadline,
                max_redirect_hops,
                self._credentials,
            )
        finally:
            self._request_slots.release()


def create_network_gateway(
    policy: NetworkPolicy,
    credentials: OriginCredentials | None = None,
    max_concurrent_requests: int = 4,
) -> NetworkGateway:
    """Build the real fixed-IP, CA-verified transport; it never reads system proxy settings."""
    return NetworkGateway(policy, credentials, max_concurrent_requests)


def fetch_with_policy(
    policy: NetworkPolicy,
    url: str,
    transport: Callable[[str], TransportResponse] | None = None,
    resolve_addresses: Callable[[str], list[str]] | None = None,
    max_redirect_hops: int = MAX_REDIRECT_HOPS,
) -> FetchResult:
    """Fetch a trusted source URL; both legacy injection arguments select explicit fixture mode."""
    if transport is None and resolve_addresses is None:
        return create_network_gateway(policy).fetch(url, max_redirect_hops)
    if transport is None or resolve_addresses is None:
        raise ValueError("fixture transport and resolver must be supplied together")
    deadline = RequestDeadline(time.monotonic() + policy.total_timeout_seconds)
    return _fetch(
        policy,
        url,
        lambda target, addresses, budget, headers: transport(target),
        lambda hostname, budget: resolve_addresses(hostname),
        deadline,
        max_redirect_hops,
    )
