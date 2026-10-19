"""TextBlock 生成与规范化: 固定块序、保留标题/列表/表格/代码/页码, 规则版本化。"""

from __future__ import annotations

from dataclasses import dataclass, field

NORMALIZER_VERSION = "1.0.0"


@dataclass(frozen=True)
class TextBlock:
    """固定文本块: 序号稳定, 类型标明结构语义, 偏移为规范化文本 Unicode code point。"""

    block_id: str
    ordinal: int
    block_type: str
    text: str
    start_offset: int
    end_offset: int
    page_number: int | None = None


@dataclass(frozen=True)
class ParseOutcome:
    """解析结果: 状态四分, partial/ambiguous/unparseable 不伪造全文。"""

    status: str
    blocks: tuple[TextBlock, ...] = field(default_factory=tuple)
    normalized_text: str = ""
    normalizer_version: str = NORMALIZER_VERSION
    parser_version: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


def build_blocks_from_segments(
    segments: list[tuple[str, str, int | None]],
    parser_version: str,
) -> ParseOutcome:
    """按段落序列生成 TextBlock: 拼接规范化文本并计算全局偏移。"""
    blocks: list[TextBlock] = []
    parts: list[str] = []
    cursor = 0
    for ordinal, (block_type, text, page_number) in enumerate(segments):
        start_offset = cursor
        parts.append(text)
        cursor += len(text)
        blocks.append(
            TextBlock(
                block_id=f"b{ordinal:04d}",
                ordinal=ordinal,
                block_type=block_type,
                text=text,
                start_offset=start_offset,
                end_offset=cursor,
                page_number=page_number,
            )
        )
    return ParseOutcome(
        status="parsed" if blocks else "unparseable",
        blocks=tuple(blocks),
        normalized_text="".join(parts),
        parser_version=parser_version,
    )
