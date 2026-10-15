"""Synthetic review probes with observable expectations; no source or model IO."""

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ai_intel.enrichment.contracts import EnrichmentBlock, EnrichmentContext, EnrichmentDocument
from ai_intel.enrichment.signal_sources import PublicSignalError, select_cwe_catalog_document
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.ingestion.parsing.parsers import parse_json_document

CVE = "CVE-2024-12345"
GHSA = "GHSA-2345-6789-cfgh"
VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
NOW = datetime(2026, 10, 15, tzinfo=UTC)


def nvd_payload(score=9.8, cve=CVE, cwes=()):
    return {"cve": {"id": cve, "metrics": {"cvssMetricV31": [
        {"source": "nvd@nist.gov", "cvssData": {"version": "3.1", "baseScore": score,
                                               "vectorString": VECTOR}}]},
        "weaknesses": [{"description": [{"lang": "en", "value": identifier}]} for identifier in cwes]}}


def vendor_payload(score=8.1, cve=CVE):
    return {"ghsa_id": GHSA, "cve_id": cve, "state": "published",
            "html_url": f"https://github.com/vllm-project/vllm/security/advisories/{GHSA}",
            "summary": "Synthetic source for independent review", "vulnerabilities": [],
            "publisher": {"login": "review-maintainer"},
            "cvss": {"score": score, "vector_string": VECTOR}, "cwes": []}


def document(payload, uri=None, kind="advisory", category="structured_vulnerability", version=None,
             coverage="full_text", complete=True, observed=NOW):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    parsed = parse_json_document(raw)
    assert parsed.status == "parsed"
    return EnrichmentDocument(
        revision_id=uuid4(), document_id=uuid4(), source_id=uuid4(), document_kind=kind,
        source_category=category, canonical_uri=uri or f"https://nvd.nist.gov/vuln/detail/{CVE}",
        source_record_id="independent-review-synthetic", content_sha256=hashlib.sha256(raw).hexdigest(),
        json_payload=raw, source_version=version, content_coverage=coverage, blocks_complete=complete,
        observed_at=observed, blocks=tuple(EnrichmentBlock(
            block_id=uuid4(), start_offset=block.start_offset, text=block.text,
            text_sha256=hashlib.sha256(block.text.encode()).hexdigest(),
            json_pointer=block.block_type.removeprefix("field:")) for block in parsed.blocks))


def attempts(*documents, cves=(CVE,)):
    context = EnrichmentContext(event_id=uuid4(), expected_event_version=1,
        revision_ids=tuple(source.revision_id for source in documents), external_cve_ids=cves,
        rule_version="independent-review-synthetic-1")
    return {attempt.dimension: attempt for attempt in enrich_structured_fields(context, documents)}


def catalog(ids=("CWE-78",), name="Command Injection"):
    xml = ("<Weakness_Catalog xmlns='http://cwe.mitre.org/cwe-7' Version='4.20'><Weaknesses>"
           "<Weakness ID='78' Name='Command Injection'/><Weakness ID='79' Name='Cross-site Scripting'/>"
           "</Weaknesses></Weakness_Catalog>").encode()
    selected = select_cwe_catalog_document(xml, ids)
    payload = json.loads(selected.payload)
    if name != "Command Injection":
        payload["weaknesses"][0]["name"] = name
    return document(payload, selected.canonical_uri, kind="standard", category="technical_standard",
                    version="4.20", coverage="metadata_only")


@pytest.mark.parametrize("uri,category", [
    (f"https://nvd.nist.gov.evil.invalid/vuln/detail/{CVE}", "structured_vulnerability"),
    (f"http://nvd.nist.gov/vuln/detail/{CVE}", "structured_vulnerability"),
    (f"https://nvd.nist.gov:444/vuln/detail/{CVE}", "structured_vulnerability"),
    (f"https://nvd.nist.gov/vuln/detail/{CVE}", "vendor_advisory"),
])
def test_bad_source_identity_has_no_available_signal(uri, category):
    result = attempts(document(nvd_payload(), uri=uri, category=category))
    assert result["cvss"].status.value == "pending"
    assert not result["cvss"].candidates


@pytest.mark.parametrize("mutation", ["wrong_text", "wrong_pointer", "duplicate_pointer"])
def test_exact_quote_and_pointer_are_required(mutation):
    source = document(nvd_payload())
    block = next(block for block in source.blocks if block.json_pointer.endswith("/baseScore"))
    if mutation == "wrong_text":
        text = block.text.replace("9.8", "0.0")
        modified = block.model_copy(update={"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    elif mutation == "wrong_pointer":
        modified = block.model_copy(update={"json_pointer": "/unrelated/same-value"})
    else:
        modified = block.model_copy(update={"block_id": uuid4()})
    blocks = tuple(modified if item.block_id == block.block_id else item for item in source.blocks)
    if mutation == "duplicate_pointer":
        blocks = source.blocks + (modified,)
    result = attempts(source.model_copy(update={"blocks": blocks}))["cvss"]
    assert result.status.value == "failed"
    assert result.error_code == "structured_evidence_mismatch"
    assert not result.candidates


@pytest.mark.parametrize("coverage", ["metadata_only", "excerpt", "unknown"])
def test_missing_metadata_is_pending_not_negative(coverage):
    result = attempts(document({"cve": {"id": CVE}}, coverage=coverage))
    assert result["cvss"].status.value == result["cwe"].status.value == "pending"
    assert not result["cvss"].candidates


@pytest.mark.parametrize("kwargs", [{"complete": False}, {"observed": None}])
def test_explicit_empty_requires_complete_scope_and_time(kwargs):
    source = document({"cve": {"id": CVE, "metrics": {}, "weaknesses": []}},
                      coverage="metadata_only", **kwargs)
    result = attempts(source)
    assert result["cvss"].status.value == result["cwe"].status.value == "pending"


def test_metadata_only_exact_fields_keep_limits_and_quote_coordinates():
    source = document(nvd_payload(), coverage="metadata_only")
    result = attempts(source)["cvss"]
    assert result.status.value == "available"
    candidate = result.candidates[0]
    assert candidate.value.scored_at is None
    assert candidate.limitations
    for evidence in candidate.evidence:
        block = next(item for item in source.blocks if item.block_id == evidence.block_id)
        assert block.text[evidence.start_offset:evidence.end_offset] == evidence.quote_text
        assert hashlib.sha256(evidence.quote_text.encode()).hexdigest() == evidence.quote_sha256


def test_good_source_survives_bad_source_with_explicit_partial_reason():
    good = document(nvd_payload())
    bad = document(nvd_payload(cve="CVE-2024-99999"))
    result = attempts(good, bad)["cvss"]
    assert result.status.value == "available" and len(result.candidates) == 1
    assert result.error_code == "partial_signal_source_failure"


def test_cwe_missing_selected_identifier_remains_blocked():
    source = document(nvd_payload(cwes=("CWE-79",)))
    result = attempts(source, catalog())["cwe"]
    assert result.status.value == "blocked" and result.error_code == "cwe_identifier_not_verified"
    assert not result.candidates


def test_cwe_selected_name_quote_mismatch_fails_only_weakness():
    source = document(nvd_payload(cwes=("CWE-78",)))
    directory = catalog()
    payload = json.loads(directory.json_payload)
    payload["weaknesses"][0]["name"] = "Unsupported replacement"
    raw = json.dumps(payload, separators=(",", ":")).encode()
    altered = directory.model_copy(update={"json_payload": raw, "content_sha256": hashlib.sha256(raw).hexdigest()})
    result = attempts(source, altered)
    assert result["cwe"].status.value == "failed"
    assert result["cwe"].error_code == "structured_evidence_mismatch"
    assert result["cvss"].status.value == "available"


@pytest.mark.parametrize("mutation", ["wrong_version", "incomplete", "invalid_hash", "extraneous_id"])
def test_invalid_cwe_selection_cannot_validate_source_identifier(mutation):
    source = document(nvd_payload(cwes=("CWE-78",)))
    directory = catalog()
    payload = json.loads(directory.json_payload)
    if mutation == "wrong_version":
        payload["taxonomy_version"] = "4.19"
    elif mutation == "incomplete":
        payload["selection"]["complete_catalog"] = False
    elif mutation == "invalid_hash":
        payload["selection"]["source_xml_sha256"] = "invalid"
    else:
        payload["weaknesses"][0]["cwe_id"] = "CWE-80"
    altered = document(payload, directory.canonical_uri, kind="standard", category="technical_standard", version="4.20")
    result = attempts(source, altered)
    assert result["cwe"].status.value == "failed" and result["cwe"].error_code == "invalid_cwe_selection"
    assert result["cvss"].status.value == "available"


def test_cwe_directory_path_and_entity_expansion_are_rejected():
    xml = b'<!DOCTYPE Weakness_Catalog [<!ENTITY e "expanded">]><Weakness_Catalog>&e;</Weakness_Catalog>'
    with pytest.raises(PublicSignalError, match="unsafe_cwe_xml"):
        select_cwe_catalog_document(xml, ("CWE-78",))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../cwec.xml", b"<root/>")
    with pytest.raises(PublicSignalError, match="invalid_cwe_archive"):
        select_cwe_catalog_document(stream.getvalue(), ("CWE-78",))


def test_same_cve_nvd_vendor_different_scores_must_conflict():
    nvd = document(nvd_payload(score=9.8))
    payload = vendor_payload(score=8.1)
    vendor = document(payload, payload["html_url"], category="vendor_advisory")
    result = attempts(nvd, vendor)["cvss"]
    assert len(result.candidates) == 2
    assert {candidate.value.base_score for candidate in result.candidates} == {9.8, 8.1}
    assert result.status.value == "conflict"


def test_unrelated_valid_cwe_selection_does_not_remove_verified_candidate():
    source = document(nvd_payload(cwes=("CWE-78",)))
    relevant = catalog(("CWE-78",))
    unrelated = catalog(("CWE-79",))
    baseline = attempts(source, relevant)["cwe"]
    assert baseline.status.value == "available" and len(baseline.candidates) == 1
    result = attempts(source, relevant, unrelated)["cwe"]
    assert result.status.value == "available"
    assert len(result.candidates) == 1
    assert result.candidates[0].value.cwe_id == "CWE-78"
