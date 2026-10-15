"""真实多公告页中的未知 package 不得变成假归属或丢失整页。"""

import json
from pathlib import Path

import pytest

from ai_intel.ingestion.sources.vendor_advisories import (
    VendorAdvisoryError,
    normalize_vendor_advisory,
)

FIXTURE = (
    Path(__file__).resolve().parents[3] / "fixtures/recorded/vllm_api_page_20261015_public.json"
)


def test_actual_ten_advisory_page_keeps_missing_package_and_source_ranges():
    records = json.loads(FIXTURE.read_bytes())
    advisories = [
        normalize_vendor_advisory(record, repository="vllm-project/vllm") for record in records
    ]
    assert len(advisories) == 10
    target = next(item for item in advisories if item.ghsa_id == "GHSA-5fj9-pfhr-6j48")
    package = target.vulnerabilities[0]
    assert package.package_ecosystem is None
    assert package.package_name is None
    assert package.affected_range == "< v0.30.0"
    assert package.patched_version == ">= 0.30.0"


@pytest.mark.parametrize("field", ["name", "ecosystem"])
@pytest.mark.parametrize(
    "invalid",
    [42, "\x00", "\ud800", " " * 10_001],
    ids=["non_string", "nul", "surrogate", "oversized_blank"],
)
def test_missing_package_normalization_still_rejects_invalid_types_and_text(field, invalid):
    record = json.loads(FIXTURE.read_bytes())[5]
    record["vulnerabilities"][0]["package"][field] = invalid
    with pytest.raises(VendorAdvisoryError):
        normalize_vendor_advisory(record, repository="vllm-project/vllm")
