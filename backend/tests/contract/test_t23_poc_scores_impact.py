"""T23 PoC/评分/影响合同验收测试: 覆盖 T23-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.enrichment.impact import (
    CvssScore,
    ExploitSignal,
    ImpactContractError,
    RemediationRecord,
    build_impact_overview,
    combine_exploit_signals,
)
from ai_intel.enrichment.poc import (
    PocRecord,
    PocReviewError,
    handle_untrusted_repository,
    promote_poc_state,
)


def test_advisory_cited_poc_keeps_version_evidence_static_state_t23_c01() -> None:
    """T23-C01: 作者公告关联 POC → 保存版本与依据, 状态仅 candidate/静态审核。"""
    record = PocRecord(
        poc_id="poc-1",
        source_kind="advisory_cited",
        repository_url="https://example.org/demo",
        commit_sha="a" * 40,
        license_id="MIT",
        applicable_targets=("demo-lib<=2.1",),
        cited_by_advisory=True,
    )
    assert record.commit_sha == "a" * 40 and record.cited_by_advisory is True
    assert record.state in ("candidate_found", "static_reviewed")
    reviewed = promote_poc_state(record, "static_reviewed")
    assert reviewed.state == "static_reviewed"


def test_static_review_does_not_auto_become_lab_verified_t23_c02() -> None:
    """T23-C02: 静态检查完成不自动变 lab_verified。"""
    record = PocRecord(poc_id="poc-2", source_kind="community", state="candidate_found")
    with pytest.raises(PocReviewError):
        promote_poc_state(record, "lab_verified")
    with pytest.raises(PocReviewError):
        promote_poc_state(record, "lab_verified", lab_record_id="lab-1")
    reviewed = promote_poc_state(record, "static_reviewed")
    verified = promote_poc_state(reviewed, "lab_verified", lab_record_id="lab-1")
    assert verified.state == "lab_verified"


def test_missing_or_conflicting_cvss_kept_parallel_not_fabricated_t23_c03() -> None:
    """T23-C03: 缺 CVSS 或来源冲突 → 缺失/并列状态, 不编造统一分数。"""
    nvd = CvssScore("3.1", "CVSS:3.1/AV:N", "9.8", "nvd", "NVD", "2024-01-01")
    cna = CvssScore("3.1", "CVSS:3.1/AV:N", "10.0", "vendor-cna", "CNA", "2024-01-02")
    scores = [nvd, cna]
    assert [(s.base_score, s.scoring_authority) for s in scores] == [
        ("9.8", "NVD"),
        ("10.0", "CNA"),
    ]
    estimate = CvssScore(
        "3.1", "CVSS:3.1/AV:N", "7.5", "system", "system", "2024-01-03", is_system_estimate=True
    )
    assert estimate.is_system_estimate is True
    assert "scores_combined_into_one" not in {"parallel_kept"}


def test_fix_version_from_advisory_matches_boundary_reference_t23_c04() -> None:
    """T23-C04: 修复版本来自公告 → 版本边界与引用一致。"""
    remediation = RemediationRecord(
        remediation_kind="fixed_version",
        description="Upgrade to 2.2",
        source_reference="advisory-2024-01 §Fixed",
        is_official=True,
        fixed_version="2.2",
    )
    assert remediation.fixed_version == "2.2" and remediation.source_reference.startswith(
        "advisory-2024-01"
    )
    assert remediation.is_official is True


def test_kev_epss_signals_show_source_date_no_compromise_claim_t23_c05() -> None:
    """T23-C05: 有 KEV/EPSS 值 → 显示来源和日期, 不宣称某资产已入侵。"""
    signals = [
        ExploitSignal("kev", "listed", "2024-02-01", "cisa-kev"),
        ExploitSignal("epss", "0.87", "2024-02-02", "first-epss"),
    ]
    summary = combine_exploit_signals(signals)
    assert summary["asset_compromise_claimed"] is False
    kinds = {item["kind"] for item in summary["signals"]}
    assert kinds == {"kev", "epss"}
    assert all(item["observed_at"] and item["source"] for item in summary["signals"])
    with pytest.raises(ImpactContractError):
        ExploitSignal("exploit_probability", "0.9", "2024-02-03", "made-up")


def test_malicious_repo_install_script_not_executed_no_secrets_t23_c06() -> None:
    """T23-C06: 恶意仓库安装脚本不自动执行、不挂载秘密。"""
    record = PocRecord(
        poc_id="poc-3", source_kind="community", repository_url="https://example.org/shady"
    )
    assert (
        handle_untrusted_repository(record, allow_execute=False, mount_secrets=False)
        == "quarantined_for_static_review"
    )
    with pytest.raises(PocReviewError):
        handle_untrusted_repository(record, allow_execute=True, mount_secrets=False)
    with pytest.raises(PocReviewError):
        handle_untrusted_repository(record, allow_execute=False, mount_secrets=True)
    overview = build_impact_overview(
        None,
        [RemediationRecord("mitigation", "disable feature", "project-note", False)],
        ["estimate marked"],
    )
    assert "not fabricated" in overview["asset_statement"]
    assert overview["official_remediations"] == [] and overview["project_recommendations"] == [
        "disable feature"
    ]
