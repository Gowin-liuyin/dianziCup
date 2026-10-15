"""Synthetic authority scopes retain all reports and only compare matching literal identities."""

import copy

import pytest
from test_r07_public_signals import attempts, document, nvd_payload
from test_r07_public_signals_fix1 import VECTOR, vendor_document


@pytest.mark.parametrize("vendor_first", [False, True])
@pytest.mark.parametrize(
    "other_authority", ["maintainer", "NVD@NIST.GOV", " nvd@nist.gov ", "unknown"]
)
def test_different_literal_authorities_keep_parallel_scores(other_authority, vendor_first):
    nvd = document(nvd_payload())
    vendor = vendor_document(score=8.1, authority=other_authority)
    sources = (vendor, nvd) if vendor_first else (nvd, vendor)
    result = attempts(*sources)["cvss"]
    assert result.status.value == "available"
    assert {(c.value.authority, c.value.base_score) for c in result.candidates} == {
        ("nvd@nist.gov", 9.8),
        (other_authority, 8.1),
    }
    assert {e.revision_id for c in result.candidates for e in c.evidence} == {
        nvd.revision_id,
        vendor.revision_id,
    }


@pytest.mark.parametrize("score,vector", [(8.1, VECTOR), (9.8, VECTOR.replace("AC:L", "AC:H"))])
def test_same_authority_and_version_conflict_survives_source_priority(score, vector):
    result = attempts(
        document(nvd_payload()),
        vendor_document(score=score, vector=vector, authority="nvd@nist.gov"),
    )["cvss"]
    assert result.status.value == "conflict"
    assert len(result.candidates) == 2
    assert {c.value.authority for c in result.candidates} == {"nvd@nist.gov"}
    assert len({(c.value.base_score, c.value.vector) for c in result.candidates}) == 2


def test_identical_same_authority_reports_keep_both_source_evidence():
    nvd, vendor = document(nvd_payload()), vendor_document(score=9.8, authority="nvd@nist.gov")
    result = attempts(nvd, vendor)["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 2
    assert {e.revision_id for c in result.candidates for e in c.evidence} == {
        nvd.revision_id,
        vendor.revision_id,
    }


@pytest.mark.parametrize(
    "version,vector",
    [
        ("2.0", "CVSS:2.0/AV:N/AC:L/Au:N/C:C/I:C/A:C"),
        ("3.0", VECTOR.replace("3.1", "3.0")),
        ("4.0", "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"),
    ],
)
def test_same_authority_different_standard_versions_are_parallel(version, vector):
    result = attempts(
        document(nvd_payload()),
        vendor_document(score=8.1, vector=vector, authority="nvd@nist.gov"),
    )["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 2
    assert {c.value.standard_version for c in result.candidates} == {"3.1", version}


@pytest.mark.parametrize("authority", [None, "", " ", 123, True, {"name": "nvd@nist.gov"}])
def test_missing_or_invalid_authority_cannot_merge_into_known_authority(authority):
    payload = nvd_payload()
    payload["cve"]["metrics"]["cvssMetricV31"][0]["source"] = authority
    result = attempts(document(payload), vendor_document(authority="maintainer"))["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 1
    assert result.candidates[0].value.authority == "maintainer"
    assert result.error_code == "partial_signal_source_failure"


def test_one_source_two_authorities_retains_exact_source_leaf_locations():
    payload = nvd_payload()
    rows = payload["cve"]["metrics"]["cvssMetricV31"]
    second = copy.deepcopy(rows[0])
    second["source"] = "cna@example.org"
    second["cvssData"]["baseScore"] = 8.1
    rows.append(second)
    source = document(payload)
    result = attempts(source)["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 2
    for index, candidate in enumerate(result.candidates):
        pointers = {
            next(b.json_pointer for b in source.blocks if b.block_id == e.block_id)
            for e in candidate.evidence
        }
        assert f"/cve/metrics/cvssMetricV31/{index}/source" in pointers
        assert f"/cve/metrics/cvssMetricV31/{index}/cvssData/baseScore" in pointers
