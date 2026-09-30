"""T09 文档解析合同验收测试: 覆盖 T09-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.ingestion.parsing.parsers import (
    parse_html_document,
    parse_json_document,
    parse_pdf_text_layer,
)
from ai_intel.ingestion.parsing.text_blocks import NORMALIZER_VERSION
from ai_intel.knowledge.evidence import (
    AmbiguousQuoteError,
    locate_evidence_span,
    render_revision_snippet,
)


def test_mixed_chinese_english_span_roundtrips_exactly_t09_c01() -> None:
    """T09-C01: 中英混合正文字符区间精确回切原文(Unicode code point)。"""
    html = "<html><body><p>漏洞影响 libdemo 组件 version 2.1 与中文描述</p></body></html>".encode()
    outcome = parse_html_document(html)
    assert outcome.status == "parsed"
    quote = "libdemo 组件 version 2.1"
    span = locate_evidence_span(outcome.blocks, quote, block_id=outcome.blocks[0].block_id)
    assert outcome.normalized_text[span.start_offset : span.end_offset] == quote


def test_table_header_and_rows_keep_relation_t09_c02() -> None:
    """T09-C02: 表格版本表头与行关系保留(block_type 区分)。"""
    html = b"<table><tr><th>version</th><th>status</th></tr><tr><td>2.1</td><td>affected</td></tr></table>"
    outcome = parse_html_document(html)
    types = [block.block_type for block in outcome.blocks]
    assert "table_header" in types and "table_row" in types
    headers = [block for block in outcome.blocks if block.block_type == "table_header"]
    rows = [block for block in outcome.blocks if block.block_type == "table_row"]
    assert [block.text for block in headers] == ["version", "status"]
    assert [block.text for block in rows] == ["2.1", "affected"]
    assert max(block.ordinal for block in headers) < min(block.ordinal for block in rows)


def test_duplicate_quote_without_block_is_ambiguous_not_random_t09_c03() -> None:
    """T09-C03: 同句两处出现且未给 block → ambiguous, 不随机匹配。"""
    html = b"<p>repeat phrase once</p><p>repeat phrase twice</p>"
    outcome = parse_html_document(html)
    with pytest.raises(AmbiguousQuoteError):
        locate_evidence_span(outcome.blocks, "repeat phrase")
    resolved = locate_evidence_span(
        outcome.blocks, "repeat phrase", block_id=outcome.blocks[1].block_id
    )
    assert resolved.block_id == outcome.blocks[1].block_id


def test_scanned_page_yields_unparseable_not_fake_fulltext_t09_c04() -> None:
    """T09-C04: 扫描页无文本层 → unparseable/partial, 不输出伪全文。"""
    outcome = parse_pdf_text_layer(b"%PDF-1.4\n%%EOF")
    assert outcome.status == "unparseable"
    assert outcome.blocks == ()
    assert any("no reliable text layer" in note for note in outcome.notes)
    html_empty = parse_html_document(b"<html><body><script>var x=1;</script></body></html>")
    assert html_empty.status == "unparseable"


def test_parser_versioning_keeps_old_spans_resolvable_t09_c05() -> None:
    """T09-C05: 解析器升级后旧 EvidenceSpan 仍按旧版本文本定位(normalizer/parser 版本记录)。"""
    html = b"<p>legacy sentence kept</p>"
    outcome = parse_html_document(html)
    assert outcome.normalizer_version == NORMALIZER_VERSION
    assert outcome.parser_version == "html-1.0.0"
    old_span = locate_evidence_span(
        outcome.blocks, "legacy sentence", block_id=outcome.blocks[0].block_id
    )
    rerun = parse_html_document(html)
    assert rerun.normalized_text[old_span.start_offset : old_span.end_offset] == "legacy sentence"


def test_malicious_html_and_cross_tenant_snippet_rejected_t09_c06() -> None:
    """T09-C06: 脚本内容不进入块; 跨租户片段展示统一 404 语义。"""
    html = b"<script>alert('xss')</script><p>safe body</p>"
    outcome = parse_html_document(html)
    joined = "".join(block.text for block in outcome.blocks)
    assert "alert" not in joined
    span = locate_evidence_span(outcome.blocks, "safe body", block_id=outcome.blocks[0].block_id)
    outsider = AccessScope.for_authenticated_user("u-b", "tenant-beta", Role.ANALYST)
    with pytest.raises(CrossTenantAccessError):
        render_revision_snippet(outcome.blocks, span, outsider, "tenant", "tenant-alpha")
    owner = AccessScope.for_authenticated_user("u-a", "tenant-alpha", Role.ANALYST)
    assert (
        render_revision_snippet(outcome.blocks, span, owner, "tenant", "tenant-alpha")
        == "safe body"
    )


def test_json_parser_reports_invalid_input_without_fabrication() -> None:
    """边界: 非法 JSON → unparseable 且 notes 说明, 不伪造解析。"""
    outcome = parse_json_document(b"{not-json")
    assert outcome.status == "unparseable"
    assert "invalid json" in outcome.notes
    valid = parse_json_document(b'{"advisory_id": "CVE-like-1", "severity": "high"}')
    assert valid.status == "parsed"
    assert any(block.block_type.startswith("field:") for block in valid.blocks)
