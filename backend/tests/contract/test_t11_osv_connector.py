"""T11 OSV 连接器合同验收测试: 覆盖 T11-C01—C06。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_intel.ingestion.sources.osv import (
    OsvContractError,
    bounded_package_query,
    normalize_osv_record,
)

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "recorded" / "osv_synthetic.json"


def load_records() -> list[dict[str, object]]:
    """加载脱敏合成 OSV 夹具。"""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    records = payload["osv_records"]
    assert isinstance(records, list)
    return records


def test_aliases_are_candidates_but_related_keeps_identity_t11_c01() -> None:
    """T11-C01: aliases 可作等价候选; related/upstream 分立保存不合并身份。"""
    record = normalize_osv_record(load_records()[0])
    assert record.aliases == ("CVE-2021-44228", "GHSA-xxxx-yyyy-zzzz")
    assert record.related == ("OSV-2021-9999",)
    assert record.upstream == ("OSV-2020-0001",)
    assert record.related != record.aliases
    assert record.osv_id not in record.related


def test_introduced_fixed_boundaries_preserved_t11_c02() -> None:
    """T11-C02: introduced/fixed 边界类型与值完整保留, 不坍缩为单一区间。"""
    record = normalize_osv_record(load_records()[0])
    ecosystem_range = record.affected[0]
    assert [(event.event_type, event.version_value) for event in ecosystem_range.events[:2]] == [
        ("introduced", "0"),
        ("fixed", "2.1"),
    ]


def test_multi_ranges_and_explicit_versions_not_lost_t11_c03() -> None:
    """T11-C03: 多区间与明确版本列表并存, 分支与排除信息不丢。"""
    record = normalize_osv_record(load_records()[0])
    first_package = record.affected[0]
    assert first_package.ranges_type == "GIT"
    assert first_package.explicit_versions == ("1.0", "1.5")
    assert len(first_package.events) == 4
    second_package = record.affected[1]
    assert second_package.ranges_type == "SEMVER"
    assert second_package.explicit_versions == ()


def test_git_ranges_keep_original_relations_t11_c04() -> None:
    """T11-C04: GIT 范围保留原始关系, 不比较 hash 大小、不转 SemVer。"""
    record = normalize_osv_record(load_records()[0])
    git_events = [
        event
        for event in record.affected[0].events
        if event.version_value.startswith(("aaaa", "bbbb"))
    ]
    assert [(event.event_type, event.version_value) for event in git_events] == [
        ("introduced", "aaaa1111"),
        ("last_affected", "bbbb2222"),
    ]
    assert all(not event.version_value.replace(".", "").isdigit() for event in git_events)


def test_osv_only_identifier_needs_no_forged_cve_t11_c05() -> None:
    """T11-C05: 无 CVE 但有 OSV 标识的事件可入库, 不伪造 CVE 别名。"""
    record = normalize_osv_record(load_records()[1])
    assert record.osv_id == "OSV-2021-0002"
    assert record.aliases == ()
    assert all(not alias.startswith("CVE-") for alias in record.aliases)
    withdrawn_record = normalize_osv_record(load_records()[2])
    assert withdrawn_record.withdrawn is True


def test_unknown_scheme_or_failure_is_explicit_with_raw_preserved_t11_c06() -> None:
    """T11-C06: 未知字段版本/响应失败明确报错, 原始记录保留不改写。"""
    unknown_scheme = normalize_osv_record(load_records()[1])
    assert unknown_scheme.affected[0].unsupported_scheme is True
    assert unknown_scheme.raw_record == load_records()[1]
    with pytest.raises(OsvContractError):
        normalize_osv_record({"modified": "2021-01-01T00:00:00Z"})
    with pytest.raises(OsvContractError):
        normalize_osv_record(
            {
                "id": "OSV-X",
                "affected": [{"ranges": [{"type": "SEMVER", "events": [{"a": "1", "b": "2"}]}]}],
            }
        )
    with pytest.raises(OsvContractError):
        bounded_package_query(lambda ecosystem, package: [], "", "")
    bounded = bounded_package_query(lambda ecosystem, package: [{"id": "OSV-1"}], "npm", "libdemo")
    assert bounded == [{"id": "OSV-1"}]
