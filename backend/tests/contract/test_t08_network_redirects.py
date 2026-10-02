"""T08 网络重定向合同验收测试: 已注册 host 被重定向到未注册 host 时必须抛错且不放行。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    fetch_with_policy,
)


@dataclass
class FakeResponse:
    """注入式响应: 网关只消费状态/头/分块。"""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    chunks: list[bytes] = field(default_factory=list)

    def iter_bytes(self) -> object:
        return iter(self.chunks)


POLICY = NetworkPolicy(allowed_domains=("registered.example",))


def test_redirect_from_registered_to_unregistered_host_is_rejected() -> None:
    """T08 结转: 已注册 host 重定向到未注册 host → 抛 NetworkPolicyViolation 且不放行。"""
    hops = {
        "https://registered.example/start": FakeResponse(
            302, {"location": "https://unregistered.example/steal"}
        ),
        "https://unregistered.example/steal": FakeResponse(
            200, {"content-type": "text/html"}, [b"leaked"]
        ),
    }
    fetched: list[str] = []

    def transport(url: str) -> FakeResponse:
        fetched.append(url)
        return hops[url]

    with pytest.raises(NetworkPolicyViolation) as captured:
        fetch_with_policy(
            POLICY, "https://registered.example/start", transport, lambda h: ["93.184.216.34"]
        )
    assert "allowlist" in str(captured.value)
    assert fetched == ["https://registered.example/start"]
