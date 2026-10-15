"""Synthetic regression inputs preserve event and selected-catalog boundaries; never live."""

import pytest
from test_r07_public_signals import CVE, attempts, document, nvd_payload

from ai_intel.enrichment import signals

GHSA = "GHSA-2345-6789-cfgh"
OTHER_GHSA = "GHSA-3456-789c-fghj"
OTHER_CVE = "CVE-2024-12345"
VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


def vendor_document(score=8.1, cve=CVE, ghsa=GHSA, vector=VECTOR, authority="maintainer"):
    payload = {
        "ghsa_id": ghsa,
        "cve_id": cve,
        "state": "published",
        "html_url": f"https://github.com/vllm-project/vllm/security/advisories/{ghsa}",
        "summary": "Synthetic regression advisory",
        "vulnerabilities": [],
        "publisher": {"login": authority},
        "cvss": {"score": score, "vector_string": vector},
        "cwes": [],
    }
    return document(payload, payload["html_url"], category="vendor_advisory")


@pytest.mark.parametrize("score,status", [(8.1, "available"), (9.8, "available")])
@pytest.mark.parametrize("vendor_first", [False, True])
def test_nvd_vendor_same_verified_cve_compares_score_and_keeps_both(score, status, vendor_first):
    nvd, vendor = document(nvd_payload()), vendor_document(score=score)
    sources = (vendor, nvd) if vendor_first else (nvd, vendor)
    result = attempts(*sources)["cvss"]
    assert result.status.value == status
    assert len(result.candidates) == 2
    assert {candidate.value.authority for candidate in result.candidates} == {
        "nvd@nist.gov",
        "maintainer",
    }
    assert {candidate.value.base_score for candidate in result.candidates} == {9.8, score}
    assert {e.revision_id for c in result.candidates for e in c.evidence} == {
        nvd.revision_id,
        vendor.revision_id,
    }


def test_same_cve_different_vector_conflicts_even_when_score_matches():
    vector = VECTOR.replace("AC:L", "AC:H")
    nvd = document(nvd_payload())
    vendor = vendor_document(score=9.8, vector=vector, authority="nvd@nist.gov")
    result = attempts(nvd, vendor)["cvss"]
    assert result.status.value == "conflict"
    assert {candidate.value.vector for candidate in result.candidates} == {VECTOR, vector}
    assert {e.revision_id for c in result.candidates for e in c.evidence} == {
        nvd.revision_id,
        vendor.revision_id,
    }


def test_two_supported_cves_are_not_collapsed_by_shared_ghsa():
    one, two = vendor_document(), vendor_document(cve=OTHER_CVE, score=4.0)
    result = attempts(one, two, cves=(CVE, OTHER_CVE))["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 2


def test_different_ghsa_aliases_of_same_supported_cve_still_conflict():
    result = attempts(vendor_document(), vendor_document(ghsa=OTHER_GHSA, score=4.0))["cvss"]
    assert result.status.value == "conflict" and len(result.candidates) == 2


@pytest.mark.parametrize("ghsa,status", [(GHSA, "conflict"), (OTHER_GHSA, "available")])
def test_ghsa_only_advisories_use_their_own_verified_identity(ghsa, status):
    result = attempts(
        vendor_document(cve=None), vendor_document(cve=None, ghsa=ghsa, score=4.0), cves=()
    )["cvss"]
    assert result.status.value == status and len(result.candidates) == 2


def test_ghsa_only_advisory_is_not_assumed_to_match_only_context_cve():
    result = attempts(document(nvd_payload()), vendor_document(cve=None))["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 2


def test_identifier_shaped_publisher_is_not_an_event_identity():
    result = attempts(document(nvd_payload()), vendor_document(authority=OTHER_CVE))["cvss"]
    assert result.status.value == "available"
    assert result.candidates[1].value.authority == OTHER_CVE


def test_cvss_comparison_is_independent_of_evidence_order(monkeypatch):
    original = signals._evidence

    def reversed_evidence(source, fields):
        return tuple(reversed(original(source, fields)))

    monkeypatch.setattr(signals, "_evidence", reversed_evidence)
    nvd, vendor = document(nvd_payload()), vendor_document(authority="nvd@nist.gov")
    result = attempts(nvd, vendor)["cvss"]
    assert result.status.value == "conflict" and len(result.candidates) == 2
    assert {e.revision_id for c in result.candidates for e in c.evidence} == {
        nvd.revision_id,
        vendor.revision_id,
    }


def test_unsupported_vendor_cve_is_rejected_without_changing_supported_scope():
    result = attempts(document(nvd_payload()), vendor_document(cve=OTHER_CVE))["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 1
    assert result.error_code == "partial_signal_source_failure"
