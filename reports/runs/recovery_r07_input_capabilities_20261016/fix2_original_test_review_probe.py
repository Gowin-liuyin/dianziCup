"""Independent offline review probes for parser and selection boundaries."""

import hashlib
import io
import json
import struct
import zipfile
from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError
from tests.unit.test_r07_input_capabilities import ATLAS_YAML, CWE_XML, long_document, provenance
from tests.unit.test_r07_model_fields import context, document, fixture_documents
from tests.unit.test_r07_single_model_dimension import prepared_transport
from tests.contract.test_r07_input_selection_codec import output_for

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.evidence_selection import select_field_evidence
from ai_intel.enrichment.contracts import CandidateEvidence, EvidenceBoundCandidate
from ai_intel.enrichment.field_sources import FieldEvidenceError, validate_field_candidate
from ai_intel.enrichment.model_fields import ExtractedVersionValue, ModelFieldProposal, extract_model_dimension, generate_model_field_attempts
from ai_intel.enrichment.taxonomy_inputs import TaxonomyInputError, parse_atlas_catalogue, parse_cwe_catalogue


@pytest.mark.parametrize("uri", ["https://cwe.mitre.org:bad/data/xml/cwec_v4.19.xml", "https://[invalid/data/xml/cwec_v4.19.xml"])
def test_invalid_uri_returns_typed_safe_error(uri):
    with pytest.raises(TaxonomyInputError, match="taxonomy_source_uri_invalid"):
        parse_cwe_catalogue(CWE_XML, provenance(CWE_XML, canonical_uri=uri))


def test_unsupported_zip_compression_returns_typed_archive_error():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("cwec_v4.19.xml", CWE_XML)
    raw = bytearray(buffer.getvalue())
    local = raw.find(b"PK\x03\x04")
    central = raw.find(b"PK\x01\x02")
    struct.pack_into("<H", raw, local + 8, 99)
    struct.pack_into("<H", raw, central + 10, 99)
    raw = bytes(raw)
    with pytest.raises(TaxonomyInputError, match="taxonomy_archive_invalid"):
        parse_cwe_catalogue(raw, provenance(raw))


def test_semantic_yaml_duplicate_keys_are_rejected():
    raw = ATLAS_YAML + b"\nmetadata:\n  true: first\n  True: second\n"
    with pytest.raises(TaxonomyInputError, match="taxonomy_yaml_duplicate_key"):
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))


@pytest.mark.parametrize("suffix", [b"\nmetadata: !!int nope\n", b"\nmetadata: !!bool nope\n", b"\nmetadata: !!float nope\n", b"\nmetadata: 2026-99-99\n"])
def test_malformed_builtin_yaml_scalar_returns_typed_error(suffix):
    raw = ATLAS_YAML + suffix
    with pytest.raises(TaxonomyInputError):
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))


@pytest.mark.parametrize("suffix", [b"\nfoo: " + b"[" * 65 + b"null" + b"]" * 65, b"\nfoo: &a value\nbar: *a", b"\nfoo: !unknown value"])
def test_yaml_resource_and_constructor_boundary(suffix):
    raw = ATLAS_YAML + suffix
    with pytest.raises(TaxonomyInputError):
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))


def test_selected_and_omitted_ranges_partition_unicode_original():
    line = "PyPI 包 affected versions: >=1.0,<2.0; only when tools enabled."
    original = "🙂无关" * 6000 + "\r\n" + line + "\r\n" + "unknown qualifier\n"
    source = document(63, original, "https://example.invalid/unicode")
    selected = select_field_evidence((source,), "versions")
    ranges = sorted([(item.start_offset, item.end_offset) for item in (*selected.selected, *selected.omitted_ranges)])
    assert ranges[0][0] == 0 and ranges[-1][1] == len(original)
    assert all(first[1] == second[0] for first, second in zip(ranges, ranges[1:], strict=False))
    assert "".join(original[start:end] for start, end in ranges) == original
    assert json.loads(selected.texts[1])["text"] == line
    assert selected.selected[0].start_offset == 18002
    with pytest.raises(FrozenInstanceError):
        selected.incomplete = False


def test_all_dimensions_are_preflighted_before_any_wire(monkeypatch):
    docs = fixture_documents()
    oversized = document(61, "unrelated " * 1800, "https://example.invalid/oversized")
    docs = (docs[1], oversized)
    client, calls = prepared_transport(monkeypatch, outputs={"atlas": {"candidates": []}})
    with pytest.raises(FieldEvidenceError, match="field_input_budget_exhausted"):
        generate_model_field_attempts(context(docs), docs, client, budget_authorized=True, content_is_private=False, egress_granted=False)
    assert calls == []


def test_omitted_source_versions_remain_full_dependencies():
    relevant = long_document()
    omitted = document(60, "context without cues", "https://example.invalid/dependency")
    originals = tuple(item.model_dump_json() for item in (relevant, omitted))
    selection = select_field_evidence((relevant, omitted), "versions")
    assert len(selection.source_versions) == 2
    assert {item.revision_id for item in selection.source_versions} == {relevant.revision_id, omitted.revision_id}
    assert (omitted.revision_id, omitted.blocks[0].block_id) in selection.omitted_block_ids
    assert tuple(item.model_dump_json() for item in (relevant, omitted)) == originals
    assert all(len(record) <= 16384 for record in selection.texts)
    assert sum(len(record.encode()) for record in selection.texts) <= 65536


def test_catalogue_hash_does_not_relabel_partial_source():
    source = long_document().model_copy(update={"content_coverage": "metadata_only", "blocks_complete": False})
    selection = select_field_evidence((source,), "versions")
    assert selection.incomplete
    record = json.loads(selection.texts[1])
    assert record["content_coverage"] == "metadata_only" and not record["blocks_complete"]
    assert record["content_sha256"] == source.content_sha256


def test_fixed_cwe_cas_has_expected_members_and_hash():
    from pathlib import Path
    digest = "f7a7705971796ac26aed238f62594e24ff028549586b37150da32d9bbd58c554"
    raw = (Path("D:/dianzi-private/r07-taxonomy-cas") / digest).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    parsed = parse_cwe_catalogue(raw, provenance(raw, canonical_uri="https://cwe.mitre.org/data/xml/cwec_v4.19.xml.zip"))
    assert len(parsed.entries) == 969
    assert {"CWE-79", "CWE-89", "CWE-94"} <= parsed.supported_ids
    assert parsed.extracted_content_sha256 == "952e31ada53436bbfc6dab873adeb00d08870eec88d00075b38defd1142b8ddb"


def test_fixed_atlas_cas_coordinates_and_legacy_members():
    from pathlib import Path
    digest = "c9c23971d0db07e2782423d795a20e78d5c2c9bcdc78fc67e24530657daaec41"
    version = "3259f388d19cbcca11bacf12a0ef97f4198f711b"
    raw = (Path("D:/dianzi-private/r07-taxonomy-cas") / digest).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    parsed = parse_atlas_catalogue(raw, provenance(raw, "atlas", snapshot_version=version, canonical_uri=f"https://raw.githubusercontent.com/mitre-atlas/atlas-data/{version}/dist/ATLAS.yaml"))
    assert parsed.content_version == "5.6.0" and len(parsed.entries) == 170
    assert "AML.T0051" in parsed.supported_ids
    for entry in parsed.entries:
        assert raw.decode()[entry.start_offset:entry.end_offset] == entry.identifier_quote
        assert entry.identifier in entry.identifier_quote


def extract_versions(source, client):
    return extract_model_dimension(context((source,)), (source,), client, dimension="versions", budget_authorized=True, content_is_private=False, egress_granted=False)


@pytest.mark.parametrize("mutation", ["legal", "false_quote", "false_boundary"])
def test_real_omitted_candidate_is_blocked_but_false_output_is_failed(monkeypatch, mutation):
    line = "PyPI widget affected versions: >=1.0,<2.0;"
    source = long_document(relevant=line)
    blocks = tuple(block.model_copy(update={"text": line, "text_sha256": hashlib.sha256(line.encode()).hexdigest()}) for block in source.blocks)
    source = source.model_copy(update={"blocks": blocks})
    outputs = output_for(source, line)
    if mutation == "false_quote":
        outputs["versions"]["candidates"][0]["evidence"][0]["quote_text"] = "x" * len(line)
    elif mutation == "false_boundary":
        outputs["versions"]["candidates"][0]["value"]["intervals"] = [{"fixed": "99.0"}]
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract_versions(source, client)
    assert result.attempts[0].status == (DimensionStatus.BLOCKED if mutation == "legal" else DimensionStatus.FAILED)
    assert result.attempts[0].candidates == () and len(calls) == 1


@pytest.mark.parametrize("mutation", ["legal", "false_boundary"])
def test_omitted_required_context_does_not_hide_other_invalid_fields(monkeypatch, mutation):
    line = "PyPI widget affected versions: >=1.0,<2.0;"
    source = document(70, "Unrelated" * 1900 + "\n" + line + "\nOnly when tools enabled.", "https://example.invalid/qualifier")
    outputs = output_for(source, line, quoted_block=source.blocks[0])
    start = source.blocks[0].text.index(line)
    outputs["versions"]["candidates"][0]["evidence"][0].update(start_offset=start, end_offset=start + len(line))
    if mutation == "false_boundary":
        outputs["versions"]["candidates"][0]["value"]["intervals"] = [{"fixed": "99.0"}]
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract_versions(source, client)
    assert result.attempts[0].status == (DimensionStatus.BLOCKED if mutation == "legal" else DimensionStatus.FAILED)
    assert result.attempts[0].candidates == () and len(calls) == 1


def test_mixed_selection_gap_and_false_candidate_is_failed(monkeypatch):
    line = "PyPI widget affected versions: >=1.0,<2.0;"
    source = long_document(relevant=line)
    blocks = tuple(block.model_copy(update={"text": line, "text_sha256": hashlib.sha256(line.encode()).hexdigest()}) for block in source.blocks)
    source = source.model_copy(update={"blocks": blocks})
    outputs = output_for(source, line)
    import copy
    invalid = copy.deepcopy(outputs["versions"]["candidates"][0])
    invalid["value"]["intervals"] = [{"fixed": "99.0"}]
    outputs["versions"]["candidates"].append(invalid)
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract_versions(source, client)
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.attempts[0].candidates == () and len(calls) == 1


def test_seen_and_omitted_required_context_together_is_failed(monkeypatch):
    line = "PyPI widget affected versions: >=1.0,<2.0;"
    source = document(71, "Unrelated" * 1900 + "\n" + line + "\nOnly when tools enabled.\nRequires affected package configuration.", "https://example.invalid/mixed-qualifiers")
    outputs = output_for(source, line, quoted_block=source.blocks[0])
    start = source.blocks[0].text.index(line)
    outputs["versions"]["candidates"][0]["evidence"][0].update(start_offset=start, end_offset=start + len(line))
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract_versions(source, client)
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.attempts[0].candidates == () and len(calls) == 1


def test_model_cannot_supply_server_context_gaps(monkeypatch):
    source = long_document()
    outputs = output_for(source, source.blocks[-1].text)
    outputs["versions"]["context_gaps"] = [{"revision_id": str(source.revision_id), "block_id": str(source.blocks[0].block_id), "start_offset": 0, "end_offset": 1}]
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract_versions(source, client)
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.attempts[0].candidates == () and len(calls) == 1


def test_context_gaps_are_immutable_and_computed_from_the_original_block():
    line = "PyPI widget affected versions: >=1.0,<2.0;"
    qualifier = "Only when tools enabled."
    source = document(72, "Unrelated" * 1900 + "\n" + line + "\n" + qualifier, "https://example.invalid/gap-coordinates")
    output = output_for(source, line, quoted_block=source.blocks[0])["versions"]["candidates"][0]
    start = source.blocks[0].text.index(line)
    output["evidence"][0].update(start_offset=start, end_offset=start + len(line))
    proposed = ModelFieldProposal[ExtractedVersionValue].model_validate(output)
    evidence = tuple(CandidateEvidence(**quote.model_dump(), quote_sha256=hashlib.sha256(quote.quote_text.encode()).hexdigest()) for quote in proposed.evidence)
    candidate = EvidenceBoundCandidate(dimension="versions", value=proposed.value, evidence=evidence, origin=ClaimOrigin.MODEL_HYPOTHESIS)
    with pytest.raises(FieldEvidenceError) as error:
        validate_field_candidate(candidate, (source,))
    assert error.value.code == "version_expression_context_missing"
    gaps = error.value.context_gaps
    assert type(gaps) is tuple and len(gaps) == 1
    gap = gaps[0]
    assert gap.revision_id == source.revision_id and gap.block_id == source.blocks[0].block_id
    assert source.blocks[0].text[gap.start_offset:gap.end_offset] == qualifier
    with pytest.raises((FrozenInstanceError, AttributeError, ValidationError)):
        gap.start_offset = 0
    assert FieldEvidenceError("ordinary_safe_code").context_gaps == ()
