"""T12 厂商公告/博客连接器合同验收测试: 覆盖 T12-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.ingestion.sources.feed import (
    FeedParseError,
    is_material_content_change,
    merge_duplicate_entries,
    normalize_feed_entry,
)


def test_rss_entry_forms_version_and_source_evidence_t12_c01() -> None:
    """T12-C01: RSS 新条目与正文自动形成版本(内容 hash)与来源证据(record ID)。"""
    entry = normalize_feed_entry(
        {
            "link": "https://example.invalid/advisory/1",
            "title": "Advisory 1",
            "published": "2021-12-01T00:00:00Z",
            "modified": "2021-12-02T00:00:00Z",
            "body": "Vendor advisory body",
        },
        "vendor",
    )
    assert entry.source_record_id.startswith("vendor:")
    assert len(entry.content_hash_sha256) == 64
    assert entry.published_at == "2021-12-01T00:00:00Z"
    assert entry.modified_at == "2021-12-02T00:00:00Z"
    assert entry.missing_fields == ()


def test_two_tracking_links_merge_without_losing_query_params_t12_c02() -> None:
    """T12-C02: 同文章两个跟踪链接归同文档, 但不误删改变内容的 query 参数。"""
    first = normalize_feed_entry(
        {
            "link": "https://example.invalid/doc?id=42&utm_source=rss",
            "title": "Doc",
            "body": "same",
        },
        "vendor",
    )
    second = normalize_feed_entry(
        {"link": "https://example.invalid/doc?id=42&fbclid=abc", "title": "Doc", "body": "same"},
        "vendor",
    )
    assert first.canonical_uri == second.canonical_uri
    assert "id=42" in first.canonical_uri
    assert "utm_source" not in first.canonical_uri and "fbclid" not in second.canonical_uri
    assert len(merge_duplicate_entries([first, second])) == 1
    different = normalize_feed_entry(
        {"link": "https://example.invalid/doc?id=43", "title": "Doc", "body": "other"}, "vendor"
    )
    assert different.canonical_uri != first.canonical_uri


def test_navigation_only_change_is_not_material_t12_c03() -> None:
    """T12-C03: 正文只有导航变化 → material_change=false。"""
    old_blocks = ["nav: home about", "article: vulnerability fixed in 2.1"]
    new_blocks = ["nav: home blog about", "article: vulnerability fixed in 2.1"]
    assert is_material_content_change(old_blocks, new_blocks) is False
    assert (
        is_material_content_change(old_blocks, ["nav: home", "article: vulnerability fixed in 2.2"])
        is True
    )


def test_vendor_advisory_and_repost_keep_distinct_identity_t12_c04() -> None:
    """T12-C04: 官方公告与转载来源身份不混淆(不同 record 前缀与 origin)。"""
    official = normalize_feed_entry(
        {"link": "https://example.invalid/a/1", "title": "A", "body": "official"}, "vendor"
    )
    repost = normalize_feed_entry(
        {"link": "https://blog.example.invalid/repost/1", "title": "A", "body": "official"}, "blog"
    )
    assert official.source_record_id != repost.source_record_id
    assert official.canonical_uri != repost.canonical_uri
    assert official.source_record_id.startswith("vendor:") and repost.source_record_id.startswith(
        "blog:"
    )


def test_missing_time_or_unreadable_body_reports_missing_not_guessed_t12_c05() -> None:
    """T12-C05: 缺时间/正文不可读明确记 missing, 不猜正文。"""
    entry = normalize_feed_entry({"link": "https://example.invalid/x", "title": "X"}, "blog")
    assert entry.published_at is None and entry.modified_at is None and entry.body_text is None
    assert set(entry.missing_fields) == {"published", "modified", "body"}
    assert entry.content_hash_sha256 == "".join([]) or len(entry.content_hash_sha256) == 64


def test_structural_change_fails_explicitly_instead_of_blank_success_t12_c06() -> None:
    """T12-C06: 源结构改变 → 解析失败进入复核, 不存空白成功。"""
    with pytest.raises(FeedParseError):
        normalize_feed_entry({"unexpected": "shape"}, "vendor")
    with pytest.raises(FeedParseError):
        normalize_feed_entry({"title": "no link"}, "blog")
