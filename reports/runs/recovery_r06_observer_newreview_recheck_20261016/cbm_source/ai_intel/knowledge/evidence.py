"""证据定位: block+quote 定位 Unicode 区间、片段 hash、歧义与越权语义。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ai_intel.domain.access import AccessScope
from ai_intel.ingestion.parsing.text_blocks import TextBlock


class AmbiguousQuoteError(ValueError):
    """同一引文多处出现且未给 block: 明确 ambiguous, 不随机匹配。"""


@dataclass(frozen=True)
class EvidenceSpanResult:
    """定位结果: 区间为规范化文本 Unicode code point, 左闭右开。"""

    block_id: str
    start_offset: int
    end_offset: int
    quote_sha256: str


def locate_evidence_span(
    blocks: tuple[TextBlock, ...],
    quote: str,
    block_id: str | None = None,
    *,
    start_offset: int | None = None,
) -> EvidenceSpanResult:
    """定位引文: 指定 block 精确定位; 未指定且多处命中返回 ambiguous, 零命中拒绝。"""
    if not quote:
        raise ValueError("empty quote")
    quote_sha256 = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    if block_id is not None:
        for block in blocks:
            if block.block_id == block_id:
                if start_offset is not None:
                    position = start_offset - block.start_offset
                    if position < 0 or block.text[position : position + len(quote)] != quote:
                        raise ValueError("quote does not match specified occurrence")
                else:
                    position = block.text.find(quote)
                    if position >= 0 and block.text.find(quote, position + 1) >= 0:
                        raise AmbiguousQuoteError("quote repeats in block; start_offset required")
                if position < 0:
                    raise ValueError("quote not found in specified block")
                return EvidenceSpanResult(
                    block_id=block.block_id,
                    start_offset=block.start_offset + position,
                    end_offset=block.start_offset + position + len(quote),
                    quote_sha256=quote_sha256,
                )
        raise ValueError("block not found")
    if start_offset is not None:
        raise ValueError("start_offset requires block_id")
    matches = [block for block in blocks if quote in block.text]
    if not matches:
        raise ValueError("quote not found")
    if len(matches) > 1 or sum(block.text.count(quote) for block in matches) > 1:
        raise AmbiguousQuoteError("quote occurs multiple times; block_id required")
    return locate_evidence_span(blocks, quote, matches[0].block_id)


def render_revision_snippet(
    blocks: tuple[TextBlock, ...],
    span: EvidenceSpanResult,
    scope: AccessScope,
    record_visibility: str,
    record_tenant_id: str | None,
) -> str:
    """按范围展示指定 revision 片段: 越权统一 404 语义; 越界区间拒绝。"""
    scope.enforce_visible(record_visibility, record_tenant_id)
    for block in blocks:
        if block.block_id == span.block_id:
            relative_start = span.start_offset - block.start_offset
            relative_end = span.end_offset - block.start_offset
            if (
                relative_start < 0
                or relative_end > len(block.text)
                or relative_start > relative_end
            ):
                raise ValueError("span outside block")
            snippet = block.text[relative_start:relative_end]
            if hashlib.sha256(snippet.encode("utf-8")).hexdigest() != span.quote_sha256:
                raise ValueError("span quote hash does not match revision text")
            return snippet
    raise ValueError("block not found")
