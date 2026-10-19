"""领域值对象: 标识、时间、区间与可见范围的边界校验。

职责: 在进入业务层之前完成输入边界校验, 把外部原始 JSON 拦在边界外;
错误输入返回可定位的字段问题, 不猜测时区、不取绝对值、不静默修正。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, field_validator

MAX_IDENTIFIER_LENGTH = 200
MAX_LABEL_LENGTH = 500


def _require_aware_utc(value: datetime) -> datetime:
    """拒绝无时区输入, 并统一换算为 UTC; 业务不接受本地时间猜测。"""
    if value.tzinfo is None:
        raise ValueError("timezone-aware datetime required (UTC contract); naive input rejected")
    return value.astimezone(UTC)


UtcTimestamp = Annotated[datetime, AfterValidator(_require_aware_utc)]


def _require_positive_length(value: int) -> int:
    """长度类字段必须为正; 负长度直接拒绝而不是取绝对值。"""
    if value <= 0:
        raise ValueError("length must be positive")
    return value


PositiveLength = Annotated[int, AfterValidator(_require_positive_length)]


class EvidenceSpan(BaseModel):
    """证据定位区间: 保存后规范文本中的 Unicode code point, 左闭右开。"""

    start_offset: Annotated[int, Field(ge=0)]
    end_offset: Annotated[int, Field(ge=0)]
    locator: Annotated[str, Field(min_length=1, max_length=MAX_LABEL_LENGTH)]

    @field_validator("end_offset")
    @classmethod
    def end_offset_must_not_precede_start(cls, end_offset: int, info: object) -> int:
        """左闭右开区间要求 end >= start; 空区间合法, 倒置区间拒绝。"""
        return end_offset

    def model_post_init(self, __context: object) -> None:
        """区间倒置属于输入错误, 不能静默交换端点。"""
        if self.end_offset < self.start_offset:
            raise ValueError(
                "evidence span must be left-closed right-open with end_offset >= start_offset"
            )


class VisibilityScope(BaseModel):
    """可见范围: public 记录 tenant_id 必须为空, tenant 记录必须非空。"""

    visibility: Annotated[str, Field(pattern="^(public|tenant)$")]
    tenant_id: str | None = None

    def model_post_init(self, __context: object) -> None:
        """public/tenant 与 tenant_id 的组合约束: 不允许含糊的中间态。"""
        if self.visibility == "public" and self.tenant_id is not None:
            raise ValueError("public record must not carry tenant_id")
        if self.visibility == "tenant" and not self.tenant_id:
            raise ValueError("tenant record requires non-empty tenant_id")


class Identifier(BaseModel):
    """业务标识: UUID 字符串为默认主键, 公开漏洞标识另存于 external_id。"""

    value: Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)]
    external_id: Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)] | None = None

    @field_validator("value")
    @classmethod
    def value_must_be_uuid_string(cls, value: str) -> str:
        """主键必须是可解析的 UUID 字符串, 不拿标题当主键。"""
        try:
            UUID(value)
        except (ValueError, AttributeError) as parse_error:
            raise ValueError(f"identifier must be a UUID string: {parse_error}") from parse_error
        return value
