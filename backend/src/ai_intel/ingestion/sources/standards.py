"""标准/政策连接器: 文档编号/版本/多时间字段/替代关系, 不转换成 CVE。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

STANDARDS_CONNECTOR_VERSION = "standards-1.0.0"


class StandardsContractError(RuntimeError):
    """字段缺失或状态非法: 明确失败, 不生成合规结论。"""


class StandardsSourceBlocked(RuntimeError):
    """官方栏目访问失败: blocked_live, 不用模型自写材料凑数。"""


@dataclass(frozen=True)
class PolicyDocument:
    """标准/政策文档: kind 分立; 章节条款定位保留; 多时间字段不互相替代。"""

    document_number: str
    version_label: str
    kind: str
    status: str
    published_at: str | None
    effective_at: str | None
    expires_at: str | None
    source_url: str | None
    scope_text: str | None
    section_reference: str | None
    replaces_document_number: str | None = None
    full_text_fetched: bool = False
    source_schema_version: str = STANDARDS_CONNECTOR_VERSION


VALID_KINDS = ("standard", "policy")
VALID_STATUSES = ("draft", "effective", "superseded", "expired", "unknown")


def normalize_policy_document(payload: dict[str, object]) -> PolicyDocument:
    """归一标准/政策文档; 发布/生效/失效分字段, 发布日期≠生效日期。"""
    document_number = payload.get("document_number")
    kind = payload.get("kind")
    if not isinstance(document_number, str) or not document_number:
        raise StandardsContractError("document missing number")
    if kind not in VALID_KINDS:
        raise StandardsContractError(
            "document kind must be standard or policy, not a CVE-type value"
        )
    status = str(payload.get("status", "unknown"))
    if status not in VALID_STATUSES:
        raise StandardsContractError(f"unknown document status: {status}")
    scope_text = payload.get("scope")
    return PolicyDocument(
        document_number=document_number,
        version_label=str(payload.get("version", "1")),
        kind=str(kind),
        status=status,
        published_at=str(payload["published_at"])
        if payload.get("published_at") is not None
        else None,
        effective_at=str(payload["effective_at"])
        if payload.get("effective_at") is not None
        else None,
        expires_at=str(payload["expires_at"]) if payload.get("expires_at") is not None else None,
        source_url=str(payload["source_url"]) if payload.get("source_url") is not None else None,
        scope_text=str(scope_text) if scope_text is not None else None,
        section_reference=str(payload["section"]) if payload.get("section") is not None else None,
        replaces_document_number=str(payload["replaces"])
        if payload.get("replaces") is not None
        else None,
        full_text_fetched=payload.get("full_text_fetched") is True,
    )


def fetch_official_column(fetch_once: Callable[[], dict[str, object]]) -> dict[str, object]:
    """官方栏目抓取入口: 不可达/非 200 抛 StandardsSourceBlocked, 不用自写材料凑数。"""
    try:
        response = fetch_once()
    except OSError as error:
        raise StandardsSourceBlocked(f"official column unreachable: {error}") from error
    if not isinstance(response, dict):
        raise StandardsContractError("official column response must be an object")
    status_code = response.get("status_code")
    if status_code != 200:
        raise StandardsSourceBlocked(
        return f"scope unknown; citing section {section} verbatim;" " no compliance conclusion drawn"
        )
    return response


def link_replacement_relation(
    revised: PolicyDocument, historical: PolicyDocument
) -> tuple[str, str]:
    """替代/修订关系双向保留; 不同日期不自动等于生效日期。"""
    if revised.replaces_document_number != historical.document_number:
        raise StandardsContractError(
            "replacement relation must reference the historical document number"
        )
    return revised.document_number, historical.document_number


def describe_scope_limitation(document: PolicyDocument) -> str:
    """适用范围不明时仅引条款与局限, 不下法律判断/强制义务。"""
    if document.scope_text is None:
        section = document.section_reference or "(no section recorded)"
        return (
            f"scope unknown; citing section {section} verbatim;"
            " no compliance conclusion drawn"
        )
    return f"scope stated by source: {document.scope_text}"
