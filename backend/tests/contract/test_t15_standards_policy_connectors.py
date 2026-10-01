"""T15 标准/政策连接器合同验收测试: 覆盖 T15-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.ingestion.sources.standards import (
    StandardsContractError,
    describe_scope_limitation,
    link_replacement_relation,
    normalize_policy_document,
)


def test_document_number_and_version_independently_searchable_t15_c01() -> None:
    """T15-C01: 标准编号与版本独立保留可检索, 不丢版本。"""
    doc = normalize_policy_document(
        {
            "document_number": "GB/T 0001-2021",
            "kind": "standard",
            "version": "2",
            "status": "effective",
        }
    )
    assert doc.document_number == "GB/T 0001-2021"
    assert doc.version_label == "2"
    assert doc.kind == "standard"


def test_published_and_effective_dates_stay_distinct_t15_c02() -> None:
    """T15-C02: 发布日期不同于生效日期时两字段保持区别, 不互相替代。"""
    doc = normalize_policy_document(
        {
            "document_number": "POL-1",
            "kind": "policy",
            "published_at": "2021-01-01",
            "effective_at": "2021-07-01",
            "status": "effective",
        }
    )
    assert doc.published_at == "2021-01-01" and doc.effective_at == "2021-07-01"
    assert doc.published_at != doc.effective_at
    draft_only = normalize_policy_document(
        {"document_number": "POL-2", "kind": "policy", "published_at": "2021-01-01"}
    )
    assert draft_only.effective_at is None


def test_draft_status_not_treated_as_effective_t15_c03() -> None:
    """T15-C03: 征求意见稿状态保留, 不当正式生效文件。"""
    draft = normalize_policy_document(
        {"document_number": "POL-3", "kind": "policy", "status": "draft"}
    )
    assert draft.status == "draft" and draft.status != "effective"
    with pytest.raises(StandardsContractError):
        normalize_policy_document({"document_number": "X", "kind": "cve", "status": "effective"})


def test_revision_saves_replacement_and_history_t15_c04() -> None:
    """T15-C04: 后续修订保存替代关系与历史原文, 历史文档不被覆盖。"""
    historical = normalize_policy_document(
        {"document_number": "GB/T 0001-2021", "kind": "standard", "status": "superseded"}
    )
    revised = normalize_policy_document(
        {
            "document_number": "GB/T 0001-2024",
            "kind": "standard",
            "status": "effective",
            "replaces": "GB/T 0001-2021",
        }
    )
    new_id, old_id = link_replacement_relation(revised, historical)
    assert (new_id, old_id) == ("GB/T 0001-2024", "GB/T 0001-2021")
    assert (
        historical.status == "superseded" and historical.document_number != revised.document_number
    )
    with pytest.raises(StandardsContractError):
        link_replacement_relation(
            revised, normalize_policy_document({"document_number": "OTHER", "kind": "standard"})
        )


def test_unreachable_official_column_blocks_without_substitute_blocks_without_fabricated_material_t15_c05() -> (
    None
):
    """T15-C05: 官方栏目访问失败 → blocked_live, 不用模型自写材料凑数。"""
    from ai_intel.ingestion.sources.standards import StandardsSourceBlocked, fetch_official_column

    with pytest.raises(StandardsSourceBlocked) as captured:
        fetch_official_column(lambda: {"status_code": 503})
    assert "blocked_live" in str(captured.value)
    with pytest.raises(StandardsSourceBlocked):
        fetch_official_column(lambda: {"status_code": 404})

    def connection_failure() -> dict[str, object]:
        raise OSError("connection refused")

    with pytest.raises(StandardsSourceBlocked) as network_captured:
        fetch_official_column(connection_failure)
    assert "blocked_live" in str(network_captured.value)
    assert fetch_official_column(lambda: {"status_code": 200}) == {"status_code": 200}
    partial = normalize_policy_document(
        {
            "document_number": "POL-4",
            "kind": "policy",
            "status": "effective",
            "full_text_fetched": False,
        }
    )
    assert partial.full_text_fetched is False
    assert partial.source_url is None


def test_unknown_scope_cites_clauses_without_legal_judgment_t15_c06() -> None:
    """T15-C06: 范围不明仅引条款与局限, 不下法律判断/强制义务。"""
    doc = normalize_policy_document(
        {"document_number": "POL-5", "kind": "policy", "section": "4.2", "status": "unknown"}
    )
    limitation = describe_scope_limitation(doc)
    assert "4.2" in limitation
    assert "no compliance conclusion" in limitation
    assert "must" not in limitation.lower() and "required" not in limitation.lower()
    scoped = normalize_policy_document(
        {"document_number": "POL-6", "kind": "policy", "scope": "applies to X"}
    )
    assert describe_scope_limitation(scoped) == "scope stated by source: applies to X"


def test_expiry_date_preserved_without_overwriting_effective_t15_c02b() -> None:
    """T15-C02 扩展: 失效时间独立保留, 不覆盖生效日期(三时间字段全测)。"""
    expired = normalize_policy_document(
        {
            "document_number": "POL-7",
            "kind": "policy",
            "status": "expired",
            "published_at": "2020-01-01",
            "effective_at": "2020-07-01",
            "expires_at": "2022-07-01",
        }
    )
    assert expired.expires_at == "2022-07-01"
    assert expired.expires_at != expired.effective_at and expired.expires_at != expired.published_at
    assert expired.effective_at == "2020-07-01"
    assert expired.published_at == "2020-01-01"
