"""Synthetic regression inputs preserve event and selected-catalog boundaries; never live."""

import json

import pytest

from ai_intel.enrichment import signals
from ai_intel.enrichment.signal_sources import select_cwe_catalog_document
from test_r07_public_signals import CVE, attempts, document, nvd_payload

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


@pytest.mark.parametrize("score,status", [(8.1, "conflict"), (9.8, "available")])
@pytest.mark.parametrize("vendor_first", [False, True])
def test_nvd_vendor_same_verified_cve_compares_score_and_keeps_both(score, status, vendor_first):
    nvd, vendor = document(nvd_payload()), vendor_document(score=score)
    sources = (vendor, nvd) if vendor_first else (nvd, vendor)
    result = attempts(*sources)["cvss"]
    assert result.status.value == status
    assert len(result.candidates) == 2
    assert {candidate.value.authority for candidate in result.candidates} == {
        "nvd@nist.gov", "maintainer"
    }
    assert {candidate.value.base_score for candidate in result.candidates} == {9.8, score}
    assert {e.revision_id for c in result.candidates for e in c.evidence} == {
        nvd.revision_id, vendor.revision_id
    }


def test_same_cve_different_vector_conflicts_even_when_score_matches():
    vector = VECTOR.replace("AC:L", "AC:H")
    result = attempts(document(nvd_payload()), vendor_document(score=9.8, vector=vector))["cvss"]
    assert result.status.value == "conflict"
    assert {candidate.value.vector for candidate in result.candidates} == {VECTOR, vector}


def test_two_supported_cves_are_not_collapsed_by_shared_ghsa():
    one, two = vendor_document(), vendor_document(cve=OTHER_CVE, score=4.0)
    result = attempts(one, two, cves=(CVE, OTHER_CVE))["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 2


def test_different_ghsa_aliases_of_same_supported_cve_still_conflict():
    result = attempts(vendor_document(), vendor_document(ghsa=OTHER_GHSA, score=4.0))["cvss"]
    assert result.status.value == "conflict" and len(result.candidates) == 2


@pytest.mark.parametrize("ghsa,status", [(GHSA, "conflict"), (OTHER_GHSA, "available")])
def test_ghsa_only_advisories_use_their_own_verified_identity(ghsa, status):
    result = attempts(vendor_document(cve=None), vendor_document(cve=None, ghsa=ghsa, score=4.0),
                      cves=())["cvss"]
    assert result.status.value == status and len(result.candidates) == 2


def test_ghsa_only_advisory_is_not_assumed_to_match_only_context_cve():
    result = attempts(document(nvd_payload()), vendor_document(cve=None))["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 2


def test_identifier_shaped_publisher_is_not_an_event_identity():
    result = attempts(document(nvd_payload()), vendor_document(authority=OTHER_CVE))["cvss"]
    assert result.status.value == "conflict"
    assert result.candidates[1].value.authority == OTHER_CVE


def test_cvss_comparison_is_independent_of_evidence_order(monkeypatch):
    original = signals._evidence

    def reversed_evidence(source, fields):
        return tuple(reversed(original(source, fields)))

    monkeypatch.setattr(signals, "_evidence", reversed_evidence)
    result = attempts(document(nvd_payload()), vendor_document())["cvss"]
    assert result.status.value == "conflict" and len(result.candidates) == 2


def test_unsupported_vendor_cve_is_rejected_without_changing_supported_scope():
    result = attempts(document(nvd_payload()), vendor_document(cve=OTHER_CVE))["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 1
    assert result.error_code == "partial_signal_source_failure"


def catalog_selection(ids, version="0.1", name="Command Injection"):
    raw = (
        f'<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-7" Version="{version}">'
        f'<Weaknesses><Weakness ID="78" Name="{name}"/>'
        '<Weakness ID="79" Name="Cross-site Scripting"/></Weaknesses></Weakness_Catalog>'
    ).encode()
    selected = select_cwe_catalog_document(raw, ids)
    return document(json.loads(selected.payload), selected.canonical_uri, "standard",
                    "technical_standard", version)


def source_weaknesses(*identifiers):
    payload = nvd_payload()
    payload["cve"]["weaknesses"] = [
        {"description": [{"lang": "en", "value": identifier}]} for identifier in identifiers
    ]
    return document(payload)


@pytest.mark.parametrize("unrelated_first", [False, True])
def test_adding_unrelated_selection_preserves_verified_cwe_candidate(unrelated_first):
    source = source_weaknesses("CWE-78")
    relevant, unrelated = catalog_selection(("CWE-78",)), catalog_selection(("CWE-79",))
    baseline = attempts(source, relevant)["cwe"]
    directories = (unrelated, relevant) if unrelated_first else (relevant, unrelated)
    result = attempts(source, *directories)["cwe"]
    assert result.status.value == "available"
    assert result.candidates == baseline.candidates


def test_two_source_ids_can_be_verified_by_disjoint_selections_of_same_catalog():
    source = source_weaknesses("CWE-78", "CWE-79")
    command, script = catalog_selection(("CWE-78",)), catalog_selection(("CWE-79",))
    result = attempts(source, command, script)["cwe"]
    assert result.status.value == "available" and len(result.candidates) == 2
    assert {candidate.value.cwe_id for candidate in result.candidates} == {"CWE-78", "CWE-79"}
    for candidate in result.candidates:
        directory = command if candidate.value.cwe_id == "CWE-78" else script
        assert {e.revision_id for e in candidate.evidence} == {source.revision_id, directory.revision_id}


def test_missing_real_id_is_not_verified_by_an_unrelated_selected_id():
    result = attempts(source_weaknesses("CWE-78", "CWE-80"), catalog_selection(("CWE-78",)),
                      catalog_selection(("CWE-79",)))["cwe"]
    assert result.status.value == "blocked" and not result.candidates
    assert result.error_code == "cwe_identifier_not_verified"


def test_explicit_catalog_missing_id_stays_blocked_after_merging():
    result = attempts(source_weaknesses("CWE-80"), catalog_selection(("CWE-78", "CWE-80")),
                      catalog_selection(("CWE-79",)))["cwe"]
    assert result.status.value == "blocked" and not result.candidates


def test_catalog_name_conflict_remains_visible_with_other_selections():
    result = attempts(source_weaknesses("CWE-78"), catalog_selection(("CWE-78",)),
                      catalog_selection(("CWE-78",), name="Different name"),
                      catalog_selection(("CWE-79",)))["cwe"]
    assert result.status.value == "conflict" and len(result.candidates) == 2
    assert {candidate.value.name for candidate in result.candidates} == {"Command Injection", "Different name"}


def test_overlapping_selections_keep_evidence_without_inventing_conflict():
    result = attempts(source_weaknesses("CWE-78", "CWE-79"), catalog_selection(("CWE-78",)),
                      catalog_selection(("CWE-78", "CWE-79")))["cwe"]
    assert result.status.value == "available" and len(result.candidates) == 3


@pytest.mark.parametrize("version,name", [("0.2", "Command Injection"), ("0.1", "Different name")])
def test_disjoint_ids_cannot_be_stitched_across_versions_or_catalog_bytes(version, name):
    result = attempts(source_weaknesses("CWE-78", "CWE-79"), catalog_selection(("CWE-78",)),
                      catalog_selection(("CWE-79",), version=version, name=name))["cwe"]
    assert result.status.value == "blocked" and not result.candidates


def test_complete_catalog_versions_are_parallel_with_explicit_versioned_values():
    result = attempts(source_weaknesses("CWE-78"), catalog_selection(("CWE-78",)),
                      catalog_selection(("CWE-78",), version="0.2", name="Updated name"))["cwe"]
    assert result.status.value == "available" and len(result.candidates) == 2
    assert {(c.value.taxonomy_version, c.value.name) for c in result.candidates} == {
        ("0.1", "Command Injection"), ("0.2", "Updated name")
    }


def test_invalid_additional_catalog_does_not_silently_validate_any_cwe():
    directory = catalog_selection(("CWE-79",))
    payload = json.loads(directory.json_payload)
    payload["selection"]["source_xml_sha256"] = "invalid"
    invalid = document(payload, directory.canonical_uri, "standard", "technical_standard", "0.1")
    result = attempts(source_weaknesses("CWE-78"), catalog_selection(("CWE-78",)), invalid)
    assert result["cwe"].status.value == "failed" and not result["cwe"].candidates
    assert result["cwe"].error_code == "invalid_cwe_selection"
    assert result["cvss"].status.value == "available"
