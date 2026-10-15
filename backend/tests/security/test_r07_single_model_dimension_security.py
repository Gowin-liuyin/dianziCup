"""Offline private-egress and authority boundaries for the one-dimension entry."""

import pytest
from tests.unit.test_r07_model_fields import fixture_documents, fixture_outputs
from tests.unit.test_r07_single_model_dimension import DIMENSIONS, extract, prepared_transport

from ai_intel.domain.enums import DimensionStatus, DocumentKind
from ai_intel.enrichment.field_sources import FieldEvidenceError
from ai_intel.infrastructure.models.clients import FixtureProvider


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_private_content_without_permission_denies_before_transport(monkeypatch, dimension):
    client, calls = prepared_transport(monkeypatch)
    result = extract(client, dimension, content_is_private=True, egress_granted=False)
    assert len(result.attempts) == 1
    assert result.attempts[0].dimension == dimension
    assert result.attempts[0].status == DimensionStatus.BLOCKED
    assert result.attempts[0].error_code == "model_egress_denied"
    assert result.model_attempts == ()
    assert calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "other"),
        ("origin", "human_confirmed"),
        ("supports_claim", True),
        ("authorization", "admin"),
        ("status", "supported"),
        ("human_confirmed", True),
    ],
)
def test_single_model_result_cannot_promote_authority(monkeypatch, field, value):
    outputs = fixture_outputs(fixture_documents())
    outputs["versions"]["candidates"][0][field] = value
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract(client, "versions")
    assert len(result.attempts) == len(result.model_attempts) == len(calls) == 1
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.attempts[0].error_code == "model_format_invalid"
    assert result.attempts[0].candidates == ()


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_asset_inventory_is_rejected_before_transport(monkeypatch, dimension):
    documents = fixture_documents()
    inventory = documents[0].model_copy(update={"document_kind": DocumentKind.ASSET_INVENTORY})
    client, calls = prepared_transport(monkeypatch)
    with pytest.raises(FieldEvidenceError, match="field_asset_inventory_forbidden"):
        extract(client, dimension, (inventory, *documents[1:]))
    assert calls == []


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_fixture_client_cannot_replace_real_runtime_client(dimension):
    with pytest.raises(FieldEvidenceError, match="field_real_client_required"):
        extract(FixtureProvider(), dimension)
