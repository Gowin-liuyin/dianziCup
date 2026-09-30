"""SourceConnector 协议与来源注册验证: 类别/权限/解析器版本/能力状态必填。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ai_intel.domain.enums import SourceCategory


class SourceRegistrationError(ValueError):
    """来源注册不完整: 缺必填项或类别非法, 拒绝注册。"""


class SourceConnector(Protocol):
    """连接器协议: 声明名称/版本/能力, 执行受限发现请求。"""

    connector_name: str
    connector_version: str
    capabilities: tuple[str, ...]

    def fetch_document(self, url: str) -> bytes: ...


@dataclass(frozen=True)
class SourceRegistration:
    """来源注册记录: 必填类别/权限/解析器版本/能力状态。"""

    source_id: str
    display_name: str
    category: SourceCategory
    base_origin: str
    permission_grant: str
    parser_version: str
    capability_status: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


def validate_registration(registration: SourceRegistration) -> None:
    """校验必填项; 任何缺失或空值拒绝, 不给默认值。"""
    missing = [
        name
        for name, value in (
            ("source_id", registration.source_id),
            ("display_name", registration.display_name),
            ("base_origin", registration.base_origin),
            ("permission_grant", registration.permission_grant),
            ("parser_version", registration.parser_version),
            ("capability_status", registration.capability_status),
        )
        if not value
    ]
    if missing:
        raise SourceRegistrationError(f"missing required fields: {','.join(missing)}")


def count_category_coverage(registrations: list[SourceRegistration]) -> dict[str, int]:
    """类别覆盖统计: 别名归并到实际类别, 8 个别名仍只算 1 个来源。"""
    coverage: dict[str, int] = {}
    seen_source_ids: set[str] = set()
    for registration in registrations:
        validate_registration(registration)
        if registration.source_id in seen_source_ids:
            continue
        seen_source_ids.add(registration.source_id)
        key = registration.category.value
        coverage[key] = coverage.get(key, 0) + 1
    return coverage
