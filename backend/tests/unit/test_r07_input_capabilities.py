"""Synthetic bounded input fixtures; no model or public requests are made."""

import hashlib
import json
from uuid import UUID

import pytest
from tests.unit.test_r07_model_fields import document, fixture_documents, quote

from ai_intel.enrichment.contracts import CandidateEvidence, EnrichmentBlock
from ai_intel.enrichment.evidence_selection import require_selected_evidence, select_field_evidence
from ai_intel.enrichment.field_sources import FieldEvidenceError
from ai_intel.enrichment.taxonomy_inputs import (
    CatalogueProvenance,
    TaxonomyInputError,
    parse_atlas_catalogue,
    parse_cwe_catalogue,
)

CWE_XML = b"""<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-7" Version="4.19">
<Weaknesses><Weakness ID="79" Name="Cross-site Scripting"/>
<Weakness ID="89" Name="SQL Injection"/></Weaknesses></Weakness_Catalog>"""
ATLAS_YAML = b"""id: ATLAS
name: ATLAS
version: 5.6.0
matrices:
  - id: ATLAS
    name: ATLAS
    techniques:
      - id: AML.T0051
        name: LLM Prompt Injection
        object-type: technique
      - id: AML.T0051.001
        name: Indirect Injection
        object-type: technique
"""


def provenance(raw, kind="cwe", **changes):
    version = "4.19" if kind == "cwe" else "a" * 40
    uri = (
        "https://cwe.mitre.org/data/xml/cwec_v4.19.xml"
        if kind == "cwe"
        else f"https://raw.githubusercontent.com/mitre/atlas-data/{version}/dist/ATLAS.yaml"
    )
    return CatalogueProvenance.model_validate(
        {
            "kind": kind,
            "canonical_uri": uri,
            "snapshot_version": version,
            "content_sha256": hashlib.sha256(raw).hexdigest(),
            **changes,
        }
    )


def long_document(
    *, relevant="PyPI widget affected versions: >=1.0,<2.0; only when tools enabled.", count=67
):
    base = document(10, "base", "https://example.invalid/long")
    texts = [f"Unrelated status record {index}." for index in range(count)]
    texts[-1] = relevant
    blocks = tuple(
        EnrichmentBlock(
            block_id=UUID(int=1000 + index),
            start_offset=index * 100,
            text=text,
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        for index, text in enumerate(texts)
    )
    return base.model_copy(update={"blocks": blocks})


def test_67_blocks_retrieves_last_relevant_block_without_losing_source_identity():
    source = long_document()
    selection = select_field_evidence((source,), "versions")
    assert len(selection.texts) == 2
    assert selection.selected[0].block_id == source.blocks[-1].block_id
    assert len(selection.omitted_block_ids) == 66
    assert selection.incomplete
    report, record = (json.loads(text) for text in selection.texts)
    assert report["selection"]["incomplete"] is True
    assert record["block_start_offset"] == 6600
    assert record["content_sha256"] == source.content_sha256
    assert record["block_text_sha256"] == source.blocks[-1].text_sha256
    assert source.blocks_complete and len(source.blocks) == 67
    assert selection.source_versions[0].revision_id == source.revision_id
    assert selection.source_versions[0].content_sha256 == source.content_sha256
    assert selection.source_versions[0].source_id == source.source_id
    assert len(selection.omitted_ranges) == 66


def test_equal_scores_are_stable_and_every_input_remains_a_dependency():
    source = long_document(relevant="Unrelated.")
    lines = tuple(
        block.model_copy(
            update={
                "text": "Affected versions <2.0.",
                "text_sha256": hashlib.sha256(b"Affected versions <2.0.").hexdigest(),
            }
        )
        for block in source.blocks
    )
    source = source.model_copy(update={"blocks": lines})
    selection = select_field_evidence((source,), "versions")
    assert select_field_evidence((source,), "versions") == selection
    assert [item.block_id for item in selection.selected] == [
        block.block_id for block in lines[:49]
    ]
    assert len(selection.texts) == 50
    assert sum(len(text.encode()) for text in selection.texts) <= 65536


def test_oversized_no_hit_input_is_not_a_negative_or_empty_success():
    with pytest.raises(FieldEvidenceError, match="field_input_budget_exhausted"):
        select_field_evidence((long_document(relevant="Unrelated."),), "versions")


def test_long_block_selects_complete_unicode_line_with_original_offsets():
    line = "PyPI 包 affected versions: >=1.0,<2.0; only when tools enabled."
    text = "无关字符" * 4500 + "\n" + line + "\nunknown qualifier\n"
    source = document(20, text, "https://example.invalid/long-block")
    selection = select_field_evidence((source,), "versions")
    selected = selection.selected[0]
    assert selected.start_offset == 18001
    assert selected.end_offset == 18001 + len(line)
    record = json.loads(selection.texts[1])
    assert record["text"] == line
    assert selection.incomplete
    evidence = CandidateEvidence(
        **quote(source, line), quote_sha256=hashlib.sha256(line.encode()).hexdigest()
    )
    require_selected_evidence((evidence,), selection)


def test_real_but_omitted_quote_cannot_be_accepted_as_model_seen_evidence():
    source = long_document()
    selection = select_field_evidence((source,), "versions")
    block = source.blocks[0]
    evidence = CandidateEvidence(
        revision_id=source.revision_id,
        block_id=block.block_id,
        start_offset=0,
        end_offset=len(block.text),
        quote_text=block.text,
        quote_sha256=block.text_sha256,
    )
    with pytest.raises(FieldEvidenceError, match="field_evidence_outside_selection"):
        require_selected_evidence((evidence,), selection)


def test_small_source_preserves_full_blocks_and_all_qualifiers():
    documents = fixture_documents()
    selection = select_field_evidence(documents, "versions")
    assert not selection.incomplete
    assert len(selection.selected) == 3
    assert all(item.start_offset == 0 for item in selection.selected)


@pytest.mark.parametrize("kind", ["cwe", "atlas"])
def test_parsed_supported_ids_are_derived_from_versioned_bytes(kind):
    raw = CWE_XML if kind == "cwe" else ATLAS_YAML
    catalogue = (parse_cwe_catalogue if kind == "cwe" else parse_atlas_catalogue)(
        raw, provenance(raw, kind)
    )
    expected = {"CWE-79", "CWE-89"} if kind == "cwe" else {"AML.T0051", "AML.T0051.001"}
    assert catalogue.supported_ids == expected
    assert catalogue.content_version == ("4.19" if kind == "cwe" else "5.6.0")
    assert catalogue.provenance.content_sha256 == hashlib.sha256(raw).hexdigest()
    assert all(entry.source_locator for entry in catalogue.entries)
    assert catalogue.extracted_content_sha256 == hashlib.sha256(raw).hexdigest()
    if kind == "atlas":
        for entry in catalogue.entries:
            assert raw.decode()[entry.start_offset : entry.end_offset] == entry.identifier_quote
            assert entry.identifier in entry.identifier_quote


@pytest.mark.parametrize("change", ["hash", "version", "uri"])
def test_provenance_mismatch_is_not_a_catalogue_absence(change):
    changes = {
        "hash": {"content_sha256": "0" * 64},
        "version": {"snapshot_version": "4.18"},
        "uri": {"canonical_uri": "https://example.invalid/catalogue.xml"},
    }[change]
    with pytest.raises(TaxonomyInputError):
        parse_cwe_catalogue(CWE_XML, provenance(CWE_XML, **changes))


@pytest.mark.parametrize(
    "raw",
    [
        CWE_XML.replace(b'ID="89"', b'ID="79"'),
        CWE_XML.replace(b'ID="79"', b'ID="0"'),
        CWE_XML.replace(b'Version="4.19"', b'Version="4.18"'),
    ],
)
def test_duplicate_invalid_or_wrong_version_cwe_is_rejected(raw):
    with pytest.raises(TaxonomyInputError):
        parse_cwe_catalogue(raw, provenance(raw))


@pytest.mark.parametrize(
    "raw",
    [
        ATLAS_YAML.replace(b"AML.T0051.001", b"AML.T0051"),
        ATLAS_YAML.replace(b"AML.T0051.001", b"AML.TA0001"),
        ATLAS_YAML.replace(b"version: 5.6.0", b"version: 5.6.0\nversion: 5.5.0"),
        b"format-version: 6.0.0\ncollection: {version: 2026.05}\ntechniques: {}",
    ],
)
def test_unsupported_atlas_formats_and_duplicate_ids_are_explicit(raw):
    with pytest.raises(TaxonomyInputError):
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))


@pytest.mark.parametrize(
    "uri",
    [
        "https://cwe.mitre.org:bad/data/xml/cwec_v4.19.xml",
        "https://[cwe.mitre.org/data/xml/cwec_v4.19.xml",
    ],
)
def test_malformed_official_uri_has_only_a_fixed_safe_error(uri):
    with pytest.raises(TaxonomyInputError) as failure:
        parse_cwe_catalogue(CWE_XML, provenance(CWE_XML, canonical_uri=uri))
    assert str(failure.value) == "taxonomy_source_uri_invalid"
    assert uri not in str(failure.value)


@pytest.mark.parametrize(
    "keys",
    [
        "true: first\n  True: second",
        "true: first\n  1: second",
        "1: first\n  1.0: second",
        "null: first\n  ~: second",
    ],
)
def test_yaml_semantic_key_collisions_are_not_silently_merged(keys):
    raw = ATLAS_YAML + ("\nmetadata:\n  " + keys + "\n").encode()
    with pytest.raises(TaxonomyInputError, match="taxonomy_yaml_duplicate_key"):
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))


@pytest.mark.parametrize("key", [".nan", ".inf", "-.inf", "!!set fixture", "[1, 2]"])
def test_yaml_nonfinite_custom_or_nonscalar_keys_are_rejected(key):
    raw = ATLAS_YAML + ("\nmetadata:\n  " + key + ": fixture\n").encode()
    with pytest.raises(TaxonomyInputError):
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))


@pytest.mark.parametrize("scalar", ["!!int nope", "!!float nope", "!!bool nope", "2026-99-99"])
def test_invalid_mature_yaml_scalar_constructor_has_a_fixed_safe_error(scalar):
    raw = ATLAS_YAML + ("\nmetadata: " + scalar + "\n").encode()
    with pytest.raises(TaxonomyInputError) as failure:
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))
    assert str(failure.value) == "taxonomy_yaml_invalid"


INVALID_YAML_SCALARS = (
    "!!timestamp nope",
    "!!timestamp ''",
    "!!timestamp 0000-01-01",
    "!!timestamp 10000-01-01",
    "!!timestamp 2026-13-01",
    "!!timestamp 2026-01-01T24:00:00Z",
    "!!timestamp 2026-01-01T00:00:00+24:00",
    "!!int ''",
    "!!int '-'",
    "!!int 0b2",
    "!!float ''",
    "!!float ':'",
    "!!bool maybe",
)
VALID_YAML_SCALARS = (
    "!!str nope",
    "!!null null",
    "!!bool true",
    "!!int 0",
    "!!int 0xff",
    "!!float 1.25",
    "!!float .nan",
    "!!float .inf",
    "!!timestamp 2026-10-16",
    "!!timestamp 9999-12-31",
    "!!timestamp 2026-10-16T06:00:00Z",
    "!!timestamp 2000-02-29",
)


@pytest.mark.parametrize("scalar", INVALID_YAML_SCALARS)
@pytest.mark.parametrize("position", ["key", "value"])
def test_mature_scalar_failures_in_keys_and_values_have_a_fixed_error(scalar, position):
    suffix = (
        f"\nmetadata:\n  {scalar}: fixture\n" if position == "key" else f"\nmetadata: {scalar}\n"
    )
    raw = ATLAS_YAML + suffix.encode()
    with pytest.raises(TaxonomyInputError) as failure:
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))
    assert str(failure.value) == "taxonomy_yaml_invalid"


@pytest.mark.parametrize("scalar", VALID_YAML_SCALARS)
def test_valid_mature_scalar_values_preserve_taxonomy_members_and_quotes(scalar):
    raw = ATLAS_YAML + f"\nmetadata: {scalar}\n".encode()
    catalogue = parse_atlas_catalogue(raw, provenance(raw, "atlas"))
    assert catalogue.supported_ids == {"AML.T0051", "AML.T0051.001"}
    for entry in catalogue.entries:
        assert raw.decode()[entry.start_offset : entry.end_offset] == entry.identifier_quote


@pytest.mark.parametrize("scalar", ["!!binary Zm9v", "!!binary not-base64", "!!binary '中文'"])
def test_binary_scalar_tags_remain_forbidden_for_catalogues(scalar):
    raw = ATLAS_YAML + f"\nmetadata: {scalar}\n".encode()
    with pytest.raises(TaxonomyInputError, match="taxonomy_yaml_tag_forbidden"):
        parse_atlas_catalogue(raw, provenance(raw, "atlas"))


def test_attribute_error_outside_scalar_construction_is_not_hidden(monkeypatch):
    def broken_identifier_projection(*args):
        raise AttributeError("fixture_business_bug")

    monkeypatch.setattr(
        "ai_intel.enrichment.taxonomy_inputs._atlas_identifier_quotes", broken_identifier_projection
    )
    with pytest.raises(AttributeError, match="fixture_business_bug"):
        parse_atlas_catalogue(ATLAS_YAML, provenance(ATLAS_YAML, "atlas"))
