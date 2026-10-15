"""T19 结构化富化单元验收测试: 覆盖 T19-C01—C06。"""

from __future__ import annotations

from ai_intel.enrichment.dimensions import dimension_status_for_kind
from ai_intel.enrichment.structured import Claim, EnrichmentLedger


def test_structured_version_and_cvss_traceable_to_source_path_t19_c01() -> None:
    """T19-C01: 结构化版本和 CVSS 原始值与来源路径可追溯。"""
    claim = Claim(
        dimension="cvss_score",
        value="9.8",
        source_record_id="src-nvd-1",
        json_path="$.containers.cna.metrics[0].cvssV3_1.baseScore",
        evidence_span_text="CVSS:3.1/AV:N/AC:L ...",
        scoring_authority="NVD",
    )
    ledger = EnrichmentLedger(fixture_mode=True)
    assert ledger.apply_claims("fp-1", [claim], "vulnerability_advisory") == "applied"
    stored = ledger.facts["cvss_score"][0]
    assert stored.value == "9.8"
    assert stored.json_path.startswith("$.containers.cna.metrics")
    assert stored.source_record_id == "src-nvd-1" and stored.scoring_authority == "NVD"
    assert stored.evidence_span_text.startswith("CVSS")


def test_paper_without_cve_marks_cvss_not_applicable_mechanism_pending_t19_c02() -> None:
    """T19-C02: 无 CVE 论文 CVSS 可 not_applicable, 论文机制维度仍待处理。"""
    assert dimension_status_for_kind("cvss_score", "research_paper") == "not_applicable"
    assert dimension_status_for_kind("paper_mechanism", "research_paper") == "available"
    assert dimension_status_for_kind("cve_id", "research_paper") == "not_applicable"
    ledger = EnrichmentLedger(fixture_mode=True)
    ledger.apply_claims("fp-paper", [Claim("cvss_score", "10.0", "src-1", "$")], "research_paper")
    assert "cvss_score" not in ledger.facts


def test_asset_query_failure_with_paper_success_saves_partial_t19_c03() -> None:
    """T19-C03: 资产查询失败但论文成功 → partial 且保留论文结果。"""
    ledger = EnrichmentLedger(fixture_mode=True)
    ledger.apply_claims(
        "fp-3",
        [Claim("paper_mechanism", "jailbreak", "src-paper-1", "$.abstract", scope="public")],
        "research_paper",
    )
    outcome = ledger.record_job_result("job-1", ["paper_mechanism"], ["affected_product"])
    assert outcome == "partial"
    assert ledger.job_results[0]["failed"] == ["affected_product"]
    assert ledger.facts["paper_mechanism"][0].value == "jailbreak"


def test_reenrichment_same_input_produces_no_duplicate_facts_t19_c04() -> None:
    """T19-C04: 重复富化相同输入 → 不生成重复事实或消息。"""
    ledger = EnrichmentLedger(fixture_mode=True)
    claim = Claim("fix_status", "patched", "src-1", "$.status")
    assert ledger.apply_claims("fp-4", [claim], "vulnerability_advisory") == "applied"
    assert ledger.apply_claims("fp-4", [claim], "vulnerability_advisory") == "idempotent_skip"
    assert ledger.apply_claims("fp-5", [claim], "vulnerability_advisory") == "applied"
    assert len(ledger.facts["fix_status"]) == 1


def test_different_scoring_authorities_recorded_side_by_side_t19_c05() -> None:
    """T19-C05: 不同评分机构并列记录, 不静默取最高分。"""
    ledger = EnrichmentLedger(fixture_mode=True)
    ledger.apply_claims(
        "fp-6a",
        [Claim("cvss_score", "9.8", "src-nvd", "$.metrics", scoring_authority="NVD")],
        "vulnerability_advisory",
    )
    ledger.apply_claims(
        "fp-6b",
        [Claim("cvss_score", "10.0", "src-cna", "$.metrics", scoring_authority="CNA")],
        "vulnerability_advisory",
    )
    scores = [(claim.value, claim.scoring_authority) for claim in ledger.facts["cvss_score"]]
    assert ("9.8", "NVD") in scores and ("10.0", "CNA") in scores
    assert len(scores) == 2


def test_private_asset_info_excluded_from_public_event_summary_t19_c06() -> None:
    """T19-C06: 私有资产信息不出现在公共事件返回中。"""
    ledger = EnrichmentLedger(fixture_mode=True)
    ledger.apply_claims(
        "fp-7",
        [
            Claim("affected_product", "public-lib", "src-1", "$.p", scope="public"),
            Claim("affected_product", "internal-host-01", "src-priv-1", "$.a", scope="private"),
        ],
        "vulnerability_advisory",
    )
    summary = ledger.public_event_summary()
    assert "internal-host-01" not in str(summary)
    assert summary["affected_product"] == ["public-lib"]
    assert ledger.private_dimensions_present() == ["affected_product"]
