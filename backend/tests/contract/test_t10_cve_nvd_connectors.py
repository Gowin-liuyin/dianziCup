"""T10 CVE/NVD 连接器合同验收测试: 覆盖 T10-C01—C06（脱敏合成 fixture 驱动）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_intel.ingestion.sources.cve import (
    ConnectorContractError,
    discover_cve_pages,
    normalize_cve_record,
)
from ai_intel.ingestion.sources.nvd import (
    NvdUnavailableError,
    fetch_with_rate_limit_guard,
    normalize_nvd_record,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "fixtures" / "recorded" / "cve_nvd_synthetic.json"
)


def load_fixture() -> dict[str, object]:
    """加载脱敏合成 fixture(明确标记非真实响应副本)。"""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_valid_cve_record_normalized_losslessly_t10_c01() -> None:
    """T10-C01: 合法 CVE 记录标识/日期/引用无损标准化, 多来源评分并列保留。"""
    fixture = load_fixture()
    records = fixture["cve_records"]
    assert isinstance(records, list)
    normalized = normalize_cve_record(records[0])  # type: ignore[arg-type]
    assert normalized.cve_id == "CVE-2021-44228"
    assert normalized.state == "PUBLISHED"
    assert normalized.published_at == "2021-12-10T00:00:00Z"
    assert normalized.references == ("https://example.invalid/ref",)
    assert dict(normalized.scores) == {"cvssV3_1": 10.0, "cvssV2_0": 9.3}
    nvd = normalize_nvd_record(load_fixture()["nvd_records"][0])  # type: ignore[index]
    assert dict(nvd.scores) == {"cvssMetricV31": 10.0, "cvssMetricV2": 9.3}
    assert nvd.weaknesses == ("CWE-502",)


def test_updated_description_yields_revision_not_new_vulnerability_t10_c02() -> None:
    """T10-C02: 同 CVE 更新描述 → 同标识修订记录, 不新增漏洞条目。"""
    fixture = load_fixture()
    records = fixture["cve_records"]
    assert isinstance(records, list)
    first = normalize_cve_record(records[0])  # type: ignore[arg-type]
    revised = normalize_cve_record(records[1])  # type: ignore[arg-type]
    assert first.cve_id == revised.cve_id
    assert first.modified_at != revised.modified_at
    assert first.description != revised.description


def test_pagination_last_and_empty_pages_terminate_without_loss_t10_c03() -> None:
    """T10-C03: 末页/空页正确终止, 不漏页不循环。"""
    pages = [
        {"items": [{"n": 1}], "is_last_page": False, "status_code": 200},
        {"items": [{"n": 2}], "is_last_page": True, "status_code": 200},
    ]
    collected = discover_cve_pages(lambda index: pages[index])
    assert [item["n"] for item in collected] == [1, 2]
    empty_run = discover_cve_pages(lambda index: {"items": [], "status_code": 200})
    assert empty_run == []
    with pytest.raises(ConnectorContractError):
        discover_cve_pages(lambda index: {"items": [{"n": index}], "status_code": 200})


def test_missing_scores_or_version_reported_not_invented_t10_c04() -> None:
    """T10-C04: 缺 CVSS/日期字段明确记 missing, 不编造默认值。"""
    fixture = load_fixture()
    records = fixture["cve_records"]
    assert isinstance(records, list)
    incomplete = normalize_cve_record(records[3])  # type: ignore[arg-type]
    assert incomplete.scores == ()
    assert incomplete.published_at is None
    assert "metrics" in incomplete.missing_fields
    assert "datePublished" in incomplete.missing_fields
    assert "description" in incomplete.missing_fields


def test_rejected_record_keeps_state_distinct_from_active_t10_c05() -> None:
    """T10-C05: rejected 记录状态正确, 不当普通活动漏洞。"""
    fixture = load_fixture()
    records = fixture["cve_records"]
    assert isinstance(records, list)
    rejected = normalize_cve_record(records[2])  # type: ignore[arg-type]
    active = normalize_cve_record(records[0])  # type: ignore[arg-type]
    assert rejected.state == "REJECTED" and active.state == "PUBLISHED"
    assert rejected.state != active.state


def test_incompatible_fields_and_rate_limit_fail_explicitly_t10_c06() -> None:
    """T10-C06: 字段不兼容契约失败; 429 有限重试后明确失败, 无假成功。"""
    with pytest.raises(ConnectorContractError):
        normalize_cve_record({"unexpected": "shape"})
    attempts = {"count": 0}

    def always_429() -> dict[str, object]:
        attempts["count"] += 1
        return {"status_code": 429}

    with pytest.raises(NvdUnavailableError):
        fetch_with_rate_limit_guard(always_429)
    assert attempts["count"] == 3
    with pytest.raises(ConnectorContractError):
        discover_cve_pages(lambda index: {"items": [], "status_code": 429})
