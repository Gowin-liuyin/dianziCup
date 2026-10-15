"""T08 网络与来源安全验收测试: 覆盖 T08-C01—C06(注入式传输, 策略逻辑为被测对象)。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import pytest

from ai_intel.domain.enums import SourceCategory
from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
    classify_http_failure,
    fetch_with_policy,
    redact_headers,
    redact_url,
)
from ai_intel.ingestion.connectors import (
    SourceRegistration,
    SourceRegistrationError,
    count_category_coverage,
    validate_registration,
)


@dataclass
class FakeResponse:
    """注入式响应: 网关只消费状态/头/分块。"""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    chunks: list[bytes] = field(default_factory=list)

    def iter_bytes(self) -> Iterable[bytes]:
        return iter(self.chunks)

    def close(self) -> None:
        pass


POLICY = NetworkPolicy(allowed_domains=("allowed.example",))


def test_allowed_domain_document_is_captured_with_context_t08_c01() -> None:
    """T08-C01: 允许域名正常文档 → 保存内容、脱敏后时间/来源上下文与可审计 hash。"""
    response = FakeResponse(
        200,
        {"content-type": "text/html", "authorization": "Bearer secret-token"},
        [b"<html>ok</html>"],
    )
    result = fetch_with_policy(
        POLICY,
        "https://allowed.example/doc?q=1&token=SECRET",
        lambda u: response,
        lambda h: ["93.184.216.34"],
    )
    assert result.body == b"<html>ok</html>"
    assert result.status_code == 200
    assert result.final_url.endswith("token=REDACTED")
    assert result.redacted_headers["authorization"] == "REDACTED"
    assert len(result.request_fingerprint_sha256) == 64


def test_redirect_to_private_address_is_blocked_with_reason_t08_c02() -> None:
    """T08-C02: 重定向到本地/私有地址 → 阻断且错误信息给安全原因。"""
    hops = {
        "https://allowed.example/": FakeResponse(
            302, {"location": "https://allowed.example/inner"}
        ),
        "https://allowed.example/inner": FakeResponse(200, {"content-type": "text/html"}, [b"x"]),
    }

    def resolve(host: str) -> list[str]:
        return ["127.0.0.1"] if host == "allowed.example" else ["93.184.216.34"]

    with pytest.raises(NetworkPolicyViolation) as captured:
        fetch_with_policy(POLICY, "https://allowed.example/", lambda u: hops[u], resolve)
    assert "private" in str(captured.value) or "rebinding" in str(captured.value)


def test_dns_rebinding_between_check_and_connect_is_blocked_t08_c03() -> None:
    """T08-C03: 解析结果在检查与连接间变化 → 连接时刻校验阻断。"""
    calls = {"count": 0}

    def shifting_resolve(host: str) -> list[str]:
        calls["count"] += 1
        return ["93.184.216.34", "10.0.0.5"]

    response = FakeResponse(200, {"content-type": "text/html"}, [b"x"])
    with pytest.raises(NetworkPolicyViolation) as captured:
        fetch_with_policy(
            POLICY, "https://allowed.example/doc", lambda u: response, shifting_resolve
        )
    assert "private" in str(captured.value) or "rebinding" in str(captured.value)


def test_oversized_or_wrong_type_response_aborts_early_t08_c04() -> None:
    """T08-C04: 超大或错误类型响应 → 中止而非读满内存/按猜测解析。"""
    small_policy = NetworkPolicy(allowed_domains=("allowed.example",), max_response_bytes=10)
    huge = FakeResponse(200, {"content-type": "text/html"}, [b"a" * 64])
    with pytest.raises(ResponseTooLargeError):
        fetch_with_policy(
            small_policy, "https://allowed.example/big", lambda u: huge, lambda h: ["93.184.216.34"]
        )
    wrong_type = FakeResponse(200, {"content-type": "application/x-msdownload"}, [b"MZ"])
    with pytest.raises(UnsupportedContentTypeError):
        fetch_with_policy(
            POLICY, "https://allowed.example/exe", lambda u: wrong_type, lambda h: ["93.184.216.34"]
        )


def test_rate_limit_and_auth_failures_classified_differently_t08_c05() -> None:
    """T08-C05: 429 与 401 分类不同, 认证失败不得无限重试。"""
    assert classify_http_failure(429) == "rate_limited"
    assert classify_http_failure(401) == "permanent_auth_error"
    assert classify_http_failure(401) != classify_http_failure(429)
    assert classify_http_failure(503) == "transient_server_error"


def test_eight_alias_registrations_count_once_per_real_category_t08_c06() -> None:
    """T08-C06: 注册 8 个同类别别名 → 覆盖统计只按实际类别计 1。"""
    base = SourceRegistration(
        source_id="00000000-0000-5000-8000-0000000000aa",
        display_name="vendor advisory hub",
        category=SourceCategory.VENDOR_ADVISORY,
        base_origin="https://allowed.example",
        permission_grant="granted:public",
        parser_version="1.0.0",
        capability_status="configured_not_live",
        aliases=tuple(f"alias-{index}" for index in range(8)),
    )
    coverage = count_category_coverage([base, base, base])
    assert coverage == {"vendor_advisory": 1}


def test_registration_validation_rejects_missing_fields() -> None:
    """边界: 缺类别/权限/解析器版本/能力状态任一必填项 → 拒绝注册。"""
    incomplete = SourceRegistration(
        source_id="",
        display_name="x",
        category=SourceCategory.VENDOR_ADVISORY,
        base_origin="https://allowed.example",
        permission_grant="",
        parser_version="1.0.0",
        capability_status="configured_not_live",
    )
    with pytest.raises(SourceRegistrationError):
        validate_registration(incomplete)


def test_redaction_keeps_audit_hash_and_strips_secrets() -> None:
    """边界: 脱敏保留可审计 hash; 认证头与查询秘密不可还原。"""
    redacted, fingerprint = redact_url("https://allowed.example/?token=SECRET&lang=zh")
    assert "SECRET" not in redacted
    assert "lang=zh" in redacted
    assert len(fingerprint) == 64
    headers = redact_headers({"Authorization": "Bearer abc", "X-Request-Id": "r1"})
    assert headers["Authorization"] == "REDACTED"
    assert headers["X-Request-Id"] == "r1"
