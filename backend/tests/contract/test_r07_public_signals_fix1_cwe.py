"""Synthetic catalog identity and selection contracts; no live authenticity claim."""

import json

import pytest
from tests.unit.test_r07_public_signals import attempts, document, nvd_payload

from ai_intel.enrichment.signal_sources import select_cwe_catalog_document


def catalog_selection(ids, version="0.1", name="Command Injection"):
    raw = (
        f'<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-7" Version="{version}">'
        f'<Weaknesses><Weakness ID="78" Name="{name}"/>'
        '<Weakness ID="79" Name="Cross-site Scripting"/></Weaknesses></Weakness_Catalog>'
    ).encode()
    selected = select_cwe_catalog_document(raw, ids)
    return document(
        json.loads(selected.payload),
        selected.canonical_uri,
        "standard",
        "technical_standard",
        version,
    )


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
        assert {e.revision_id for e in candidate.evidence} == {
            source.revision_id,
            directory.revision_id,
        }


def test_missing_real_id_is_not_verified_by_an_unrelated_selected_id():
    result = attempts(
        source_weaknesses("CWE-78", "CWE-80"),
        catalog_selection(("CWE-78",)),
        catalog_selection(("CWE-79",)),
    )["cwe"]
    assert result.status.value == "blocked" and not result.candidates
    assert result.error_code == "cwe_identifier_not_verified"


def test_explicit_catalog_missing_id_stays_blocked_after_merging():
    result = attempts(
        source_weaknesses("CWE-80"),
        catalog_selection(("CWE-78", "CWE-80")),
        catalog_selection(("CWE-79",)),
    )["cwe"]
    assert result.status.value == "blocked" and not result.candidates


def test_catalog_name_conflict_remains_visible_with_other_selections():
    result = attempts(
        source_weaknesses("CWE-78"),
        catalog_selection(("CWE-78",)),
        catalog_selection(("CWE-78",), name="Different name"),
        catalog_selection(("CWE-79",)),
    )["cwe"]
    assert result.status.value == "conflict" and len(result.candidates) == 2
    assert {candidate.value.name for candidate in result.candidates} == {
        "Command Injection",
        "Different name",
    }


def test_overlapping_selections_keep_evidence_without_inventing_conflict():
    result = attempts(
        source_weaknesses("CWE-78", "CWE-79"),
        catalog_selection(("CWE-78",)),
        catalog_selection(("CWE-78", "CWE-79")),
    )["cwe"]
    assert result.status.value == "available" and len(result.candidates) == 3


@pytest.mark.parametrize("version,name", [("0.2", "Command Injection"), ("0.1", "Different name")])
def test_disjoint_ids_cannot_be_stitched_across_versions_or_catalog_bytes(version, name):
    result = attempts(
        source_weaknesses("CWE-78", "CWE-79"),
        catalog_selection(("CWE-78",)),
        catalog_selection(("CWE-79",), version=version, name=name),
    )["cwe"]
    assert result.status.value == "blocked" and not result.candidates


def test_complete_catalog_versions_are_parallel_with_explicit_versioned_values():
    result = attempts(
        source_weaknesses("CWE-78"),
        catalog_selection(("CWE-78",)),
        catalog_selection(("CWE-78",), version="0.2", name="Updated name"),
    )["cwe"]
    assert result.status.value == "available" and len(result.candidates) == 2
    assert {(c.value.taxonomy_version, c.value.name) for c in result.candidates} == {
        ("0.1", "Command Injection"),
        ("0.2", "Updated name"),
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
