"""Synthetic declared-span fixtures retain stored origins while checking real field semantics."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from tests.unit import test_r07_model_fields as fields
from tests.unit.test_r18_public_producer_fix2_declared import declared_rows

from ai_intel.api.public_extension_reads import PublicExtensionReadService
from ai_intel.domain.enums import ClaimOrigin
from ai_intel.enrichment.field_sources import validate_field_candidate


def declared_case(dimension, origin, quotes=None):
    documents = fields.fixture_documents()
    original = fields.fixture_outputs(documents)[dimension]["candidates"][0]
    value = {
        "kind": {
            "atlas": "atlas_mapping",
            "versions": "version_assertion",
            "literature": "literature_reference",
            "poc": "artifact_reference",
        }[dimension],
        **original["value"],
    }
    if dimension == "literature":
        value.update(
            target_document_id=str(documents[2].document_id),
            target_revision_id=str(documents[2].revision_id),
        )
    elif dimension == "poc":
        value["static_status"] = "candidate_found"
    rows = declared_rows(value, quotes or original["evidence"], documents)
    for row in rows:
        row["claim_origin"] = origin
    by_revision = {document.revision_id: document for document in documents}
    service = object.__new__(PublicExtensionReadService)
    service.graph = SimpleNamespace(
        _load_document=lambda revision, cache: (by_revision[revision], None)
    )
    return service, SimpleNamespace(dimension=dimension), rows


@pytest.mark.parametrize("dimension", ["atlas", "versions", "literature", "poc"])
@pytest.mark.parametrize(
    "origin", ["source_explicit", "structured_source", "rule_derived", "human_confirmed"]
)
def test_qualified_origins_use_real_declared_field_validation(monkeypatch, dimension, origin):
    service, projection, rows = declared_case(dimension, origin)
    original_rows = [dict(row) for row in rows]
    candidates = []

    def validate(candidate, documents):
        candidates.append(candidate)
        return validate_field_candidate(candidate, documents)

    monkeypatch.setattr("ai_intel.api.public_extension_reads.validate_field_candidate", validate)
    assert service._claim_has_declared_support(projection, rows, {}) is True
    assert len(candidates) == 1
    expected_origin = "source_explicit" if origin == "human_confirmed" else origin
    assert candidates[0].origin == ClaimOrigin(expected_origin)
    assert {item.quote_text for item in candidates[0].evidence} == {row["quote"] for row in rows}
    assert rows == original_rows
    assert all(row["claim_origin"] == origin for row in rows)


@pytest.mark.parametrize("dimension", ["atlas", "versions", "literature", "poc"])
@pytest.mark.parametrize("origin", ["model_hypothesis", "unknown"])
def test_unqualified_origins_cannot_gain_public_dimension_support(dimension, origin):
    service, projection, rows = declared_case(dimension, origin)
    claim_id = uuid4()
    revision_id = uuid4()
    projection.claim_ids = (claim_id,)
    projection.citations = (SimpleNamespace(evidence_id=uuid4(), revision_id=revision_id),)
    projection.freshness = SimpleNamespace(value="current")
    assert service._dimension_is_supported(uuid4(), projection, set(), {str(revision_id)}) is False
    if origin == "unknown":
        assert service._claim_has_declared_support(projection, rows, {}) is False
    else:
        assert service._claim_has_declared_support(projection, rows, {}) is True
    assert all(row["claim_origin"] == origin for row in rows)


@pytest.mark.parametrize("dimension", ["atlas", "versions", "literature", "poc"])
def test_human_confirmation_does_not_replace_missing_field_support(dimension):
    documents = fields.fixture_documents()
    quotes = [fields.quote(documents[0], fields.LITERATURE_LINE)]
    if dimension == "literature":
        quotes = [fields.quote(documents[0], fields.VERSION_LINE)]
    service, projection, rows = declared_case(dimension, "human_confirmed", quotes)
    assert service._claim_has_declared_support(projection, rows, {}) is False


@pytest.mark.parametrize("selected", [(0,), (1, 2), (0, 2), (0, 1), (2,)])
def test_human_version_requires_each_declared_semantic_support(selected):
    documents = fields.fixture_documents()
    original = fields.fixture_outputs(documents)["versions"]["candidates"][0]
    quotes = [original["evidence"][index] for index in selected]
    service, projection, rows = declared_case("versions", "human_confirmed", quotes)
    assert service._claim_has_declared_support(projection, rows, {}) is False


def test_human_confirmation_does_not_replace_declared_coordinate_identity():
    service, projection, rows = declared_case("versions", "human_confirmed")
    rows[0]["start_offset"] += 1
    rows[0]["end_offset"] += 1
    assert service._claim_has_declared_support(projection, rows, {}) is False
