"""HTTP 请求网关: 白名单、逐跳重定向校验、大小/类型限制、限流分类与秘密脱敏。

安全边界: 每次连接都校验目标地址(防 DNS 重绑定), 默认拒绝自由 URL 抓取;
解析地址与实际连接一致性由 transport 层连接钩子强制。
"""

from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECT_HOPS = 5
ALLOWED_SCHEMES = ("https", "http")
SENSITIVE_QUERY_KEYS = {
    "token",
    "key",
    "api_key",
    "apikey",
    "secret",
    "password",
    "sig",
    "signature",
}
SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "proxy-authorization", "x-api-key"}


class NetworkPolicyViolation(PermissionError):
    """网络策略拒绝: 域名/协议/地址/大小/类型任一越界, 记录安全原因。"""


class ResponseTooLargeError(RuntimeError):
    """响应超限: 中止读取而非读满内存。"""


class UnsupportedContentTypeError(RuntimeError):
    """内容类型不符: 中止而非按猜测解析。"""


@dataclass(frozen=True)
class FetchResult:
    """抓取结果: 脱敏后的可审计表示。"""

    final_url: str
    status_code: int
    content_type: str
    body: bytes
    redacted_headers: dict[str, str] = field(default_factory=dict)
    request_fingerprint_sha256: str = ""


class TransportResponse(Protocol):
    """传输层响应协议: 网关只依赖状态/头/流式内容。"""

    status_code: int
    headers: dict[str, str]

    def iter_bytes(self) -> object: ...


def is_private_or_local(address: str) -> bool:
    """判定地址是否私有/环回/链路本地; 非 IP 主机名按不允许处理。"""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved


def redact_url(url: str) -> tuple[str, str]:
    """脱敏 URL 查询秘密: 返回脱敏 URL 与保留可审计 hash。"""
    parts = urlsplit(url)
    redacted_pairs = [
        (key, "REDACTED" if key.lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    redacted_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(redacted_pairs), parts.fragment)
    )
    fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return redacted_url, fingerprint


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """脱敏认证头与 Cookie, 保留其余可审计头。"""
    return {
        key: ("REDACTED" if key.lower() in SENSITIVE_HEADERS else value)
        for key, value in headers.items()
    }


def classify_http_failure(status_code: int) -> str:
    """失败分类: 429 限流可退避重试; 401 认证永久失败, 不得无限重试。"""
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
    """抓取策略: 允许域名与出口校验, 默认拒绝一切未登记目标。"""

    allowed_domains: tuple[str, ...]
    max_response_bytes: int = MAX_RESPONSE_BYTES
    allowed_content_types: tuple[str, ...] = (
        "text/html",
        "application/json",
        "application/pdf",
        "text/plain",
    )

    def ensure_url_allowed(self, url: str) -> None:
        """协议与域名白名单校验; 非登记域名一律拒绝。"""
        parts = urlsplit(url)
        if parts.scheme not in ALLOWED_SCHEMES:
            raise NetworkPolicyViolation(f"scheme not allowed: {parts.scheme}")
        hostname = parts.hostname or ""
        if not any(
            hostname == allowed or hostname.endswith("." + allowed)
            for allowed in self.allowed_domains
        ):
            raise NetworkPolicyViolation("domain not in allowlist")

    def ensure_target_address_allowed(self, address: str) -> None:
        """连接时刻地址校验: 私有/本地地址阻断, 防 DNS 检查后重绑定。"""
        if is_private_or_local(address):
            raise NetworkPolicyViolation(
                "resolved address is private or local (possible DNS rebinding)"
            )


def fetch_with_policy(
    policy: NetworkPolicy,
    url: str,
    transport: object,
    resolve_addresses: object,
    max_redirect_hops: int = MAX_REDIRECT_HOPS,
) -> FetchResult:
    """经策略网关抓取: 逐跳重定向校验、连接时刻地址校验、大小/类型限制。"""
    current_url = url
    for _hop in range(max_redirect_hops + 1):
        policy.ensure_url_allowed(current_url)
        for address in resolve_addresses(urlsplit(current_url).hostname or ""):
            policy.ensure_target_address_allowed(str(address))
        response = transport(current_url)
        status_code = int(response.status_code)
        if status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location", "")
            if not location:
                raise NetworkPolicyViolation("redirect without location header")
            current_url = location
            continue
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if content_type and not any(
            content_type.startswith(allowed) for allowed in policy.allowed_content_types
        ):
            raise UnsupportedContentTypeError(f"unsupported content type: {content_type}")
        body = b""
        for chunk in response.iter_bytes():  # type: ignore[union-attr]
            body += chunk
            if len(body) > policy.max_response_bytes:
                raise ResponseTooLargeError(
                    "response exceeded size limit; aborted before buffering all"
                )
        redacted_url, fingerprint = redact_url(current_url)
        return FetchResult(
            final_url=redacted_url,
            status_code=status_code,
            content_type=content_type,
            body=body,
            redacted_headers=redact_headers(dict(response.headers)),
            request_fingerprint_sha256=fingerprint,
        )
    raise NetworkPolicyViolation("redirect hop limit exceeded")
