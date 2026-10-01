"""T21 实体/主张/冲突集成验收测试: 覆盖 T21-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.knowledge.claims import ClaimEvidence, ClaimRecord, ClaimsContractError, ClaimsLedger
from ai_intel.knowledge.entities import (
    EntityMergeConflictError,
    EntityRecord,
    can_merge_entities,
    canonicalize_entity,
    resolve_alias,
)


def make_claim(
    claim_id: str, visibility: str = "public", tenant: str = "t1", kind: str = "explicit"
) -> ClaimRecord:
    """构造主张记录。"""
    return ClaimRecord(
        claim_id=claim_id,
        dimension="affected_version",
        value="2.1",
        scope="product-a",
        effective_at="2024-01-01",
        tenant_id=tenant,
        visibility=visibility,
        evidences=(
            ClaimEvidence("src-1", "Version 2.1 is affected.", kind, supports_conclusion=True),
        ),
    )


def test_same_name_package_across_ecosystems_not_merged_t21_c01() -> None:
    """T21-C01: 同名包不同生态 → 两实体不合并。"""
    pypi_key = canonicalize_entity("package", "pypi", "demo-lib")
    npm_key = canonicalize_entity("package", "npm", "demo-lib")
    assert pypi_key.key_text() != npm_key.key_text()
    left = EntityRecord(pypi_key, hard_identifiers=("pypi:demo-lib",))
    right = EntityRecord(npm_key, hard_identifiers=("npm:demo-lib",))
    with pytest.raises(EntityMergeConflictError):
        can_merge_entities(left, right)


def test_explicit_alias_with_source_normalizes_traceably_t21_c02() -> None:
    """T21-C02: 明确 alias 有来源 → 归一且可追溯依据。"""
    key = canonicalize_entity("product", "pypi", "demo-lib")
    entity = EntityRecord(key, aliases=(("demolib", "src-vendor-1"),))
    assert resolve_alias(entity, "demolib") == key.key_text()
    traceable = [source for alias, source in entity.aliases if alias == "demolib"]
    assert traceable == ["src-vendor-1"]
    assert resolve_alias(entity, "demolib-approx") is None


def test_same_scope_exclusive_versions_become_disputed_not_vote_t21_c03() -> None:
    """T21-C03: 同 scope 互斥版本结论 → 冲突并列、不多数投票。"""
    ledger = ClaimsLedger()
    ledger.add_claim(make_claim("c1"))
    ledger.add_claim(make_claim("c2"))
    assert ledger.register_dispute("c1", "c2", reason_same_scope_exclusive=True) == "disputed"
    assert ledger.disputes == [("c1", "c2")]
    assert ledger.claims["c1"].value == ledger.claims["c2"].value
    assert ledger.register_dispute("c1", "c2", reason_same_scope_exclusive=False) == "parallel_kept"
    assert len(ledger.disputes) == 1


def test_vendor_self_revision_keeps_history_with_supersedes_t21_c04() -> None:
    """T21-C04: 厂商公告自修订 → 历史保留并有替代关系。"""
    ledger = ClaimsLedger()
    ledger.add_claim(make_claim("c-old"))
    ledger.add_claim(make_claim("c-new"))
    ledger.register_supersede("c-old", "c-new")
    assert ledger.supersedes == [("c-old", "c-new")]
    assert "c-old" in ledger.claims and "c-new" in ledger.claims


def test_source_404_only_changes_retrieval_status_t21_c05() -> None:
    """T21-C05: 来源 404 → 旧事实不自动 withdrawn, 只改获取状态。"""
    ledger = ClaimsLedger()
    ledger.add_claim(make_claim("c1"))
    assert ledger.mark_source_retrieval_status("src-1", 404) == "not_found"
    assert ledger.claims["c1"].state == "current"
    assert ledger.retrieval_status == {"src-1": "not_found"}


def test_cross_tenant_or_private_evidence_excluded_from_public_results_t21_c06() -> None:
    """T21-C06: 跨 tenant 事实或私有证据不进入公共知识结果。"""
    ledger = ClaimsLedger()
    ledger.add_claim(make_claim("c-public"))
    ledger.add_claim(make_claim("c-private", visibility="private"))
    ledger.add_claim(make_claim("c-other-tenant", tenant="t2"))
    public_ids = [claim.claim_id for claim in ledger.query_public_current("t1")]
    assert public_ids == ["c-public"]
    event = ledger.publish_claims("t1", "epoch-1", ["c-public", "c-private", "c-other-tenant"])
    assert event["published_claim_ids"] == ["c-public"]
    assert event["transactional"] is True
    hypothesis = ClaimRecord(
        claim_id="c-hyp",
        dimension="affected_version",
        value="9.9",
        scope="product-a",
        effective_at=None,
        tenant_id="t1",
        visibility="public",
        evidences=(ClaimEvidence("src-m", "model guess", "model_hypothesis"),),
        state="published",
    )
    with pytest.raises(ClaimsContractError):
        ledger.add_claim(hypothesis)


def test_hard_identifier_conflict_blocks_merge_and_overlap_merges_t21_c01b() -> None:
    """T21-C01 扩展: 同生态硬 ID 不相交→拒绝; 相交或为空→合并成功(补分支覆盖)。"""
    key = canonicalize_entity("package", "pypi", "demo-lib")
    left = EntityRecord(key, hard_identifiers=("pypi:demo-lib",))
    right = EntityRecord(key, hard_identifiers=("pypi:other",))
    with pytest.raises(EntityMergeConflictError):
        can_merge_entities(left, right)
    overlapping = EntityRecord(key, hard_identifiers=("pypi:demo-lib",))
    assert can_merge_entities(left, overlapping) is True
    assert can_merge_entities(left, EntityRecord(key)) is True


def test_hypothesis_and_withdrawn_claims_never_published_t21_c06b() -> None:
    """T21-C06 扩展: hypothesis/withdrawn 主张不进发布 outbox(发布路径负例)。"""
    ledger = ClaimsLedger()
    hypothesis = ClaimRecord(
        claim_id="c-hyp-live",
        dimension="affected_version",
        value="9.9",
        scope="product-a",
        effective_at=None,
        tenant_id="t1",
        visibility="public",
        evidences=(ClaimEvidence("src-m", "model guess", "model_hypothesis"),),
        state="current",
    )
    assert ledger.add_claim(hypothesis) == "hypothesis"
    ledger.add_claim(make_claim("c-withdrawn"))
    ledger.claims["c-withdrawn"] = ClaimRecord(
        **{**ledger.claims["c-withdrawn"].__dict__, "state": "withdrawn"}
    )
    ledger.add_claim("c-ok" and make_claim("c-ok"))
    event = ledger.publish_claims("t1", "epoch-2", ["c-hyp-live", "c-withdrawn", "c-ok"])
    assert event["published_claim_ids"] == ["c-ok"]
