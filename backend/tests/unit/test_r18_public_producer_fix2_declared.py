"""The public semantic gate uses the declared spans for every typed field owner."""

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from tests.unit import test_r07_model_fields as fields

from ai_intel.api.public_extension_reads import PublicExtensionReadService
from ai_intel.enrichment.contracts import DIMENSION_BY_VALUE_KIND
from ai_intel.enrichment.field_sources import validate_field_candidate


def declared_rows(value, quotes, documents):
    by_revision = {str(document.revision_id): document for document in documents}
    return [
        {
            "schema_version": 3,
            "predicate": value["kind"],
            "value_kind": value["kind"],
            "object_json": value,
            "claim_origin": "source_explicit",
            "revision_id": item["revision_id"],
            "block_id": item["block_id"],
            "block_start": by_revision[item["revision_id"]].blocks[0].start_offset,
            "start_offset": item["start_offset"]
            + by_revision[item["revision_id"]].blocks[0].start_offset,
            "end_offset": item["end_offset"]
            + by_revision[item["revision_id"]].blocks[0].start_offset,
            "quote": item["quote_text"],
            "quote_sha256": hashlib.sha256(item["quote_text"].encode()).hexdigest(),
        }
        for item in quotes
    ]


@pytest.mark.parametrize("dimension", ["atlas", "versions", "literature", "poc"])
@pytest.mark.parametrize("complete", [True, False])
def test_declared_field_set_is_semantically_rechecked(monkeypatch, dimension, complete):
    documents = fields.fixture_documents()
    original = fields.fixture_outputs(documents)[dimension]["candidates"][0]
    kind = next(kind for kind, owned in DIMENSION_BY_VALUE_KIND.items() if owned == dimension)
    value = {"kind": kind, **original["value"]}
    if dimension == "poc":
        value["static_status"] = "candidate_found"
    if dimension == "literature":
        value.update(
            target_document_id=str(documents[2].document_id),
            target_revision_id=str(documents[2].revision_id),
        )
    quotes = original["evidence"]
    if not complete:
        quotes = (
            quotes[-1:]
            if dimension in {"atlas", "versions"}
            else [fields.quote(documents[0], fields.VERSION_LINE)]
        )
    by_revision = {document.revision_id: document for document in documents}
    calls = []

    def validate(candidate, selected):
        calls.append(candidate)
        return validate_field_candidate(candidate, selected)

    monkeypatch.setattr("ai_intel.api.public_extension_reads.validate_field_candidate", validate)
    service = object.__new__(PublicExtensionReadService)
    service.graph = SimpleNamespace(
        _load_document=lambda revision, cache: (by_revision[revision], None)
    )
    result = service._claim_has_declared_support(
        SimpleNamespace(dimension=dimension), declared_rows(value, quotes, documents), {}
    )
    assert result is complete
    assert len(calls) == 1
    assert {item.quote_text for item in calls[0].evidence} == {
        item["quote_text"] for item in quotes
    }


@pytest.mark.parametrize(
    "kind,value",
    [
        (
            "cvss_signal",
            {
                "standard_version": "3.1",
                "base_score": 5.0,
                "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
                "authority": "Fixture",
            },
        ),
        (
            "epss_signal",
            {
                "cve_id": "CVE-2026-1234",
                "probability": 0.1,
                "percentile": 0.2,
                "data_date": "2026-10-16",
            },
        ),
        (
            "kev_signal",
            {
                "cve_id": "CVE-2026-1234",
                "catalog_version": "fixture-1",
                "date_added": "2026-10-16",
                "required_action": "Apply vendor update.",
            },
        ),
        ("weakness", {"cwe_id": "CWE-79", "taxonomy_version": "fixture-1", "name": "Fixture"}),
        (
            "exposure_aggregate",
            {
                "provider": "hunter",
                "query_id": "fixture",
                "query_version": "1",
                "service_count": 0,
                "retrieved_at": datetime.now(UTC),
                "ttl_seconds": 60,
                "limitations": ["Synthetic aggregate."],
            },
        ),
    ],
)
def test_unowned_signal_dimensions_never_borrow_field_or_graph_support(kind, value):
    documents = fields.fixture_documents()
    rows = declared_rows(
        {"kind": kind, **value}, [fields.quote(documents[0], fields.VERSION_LINE)], documents
    )
    service = object.__new__(PublicExtensionReadService)
    service.graph = SimpleNamespace(_load_document=lambda revision, cache: (documents[0], None))
    assert (
        service._claim_has_declared_support(
            SimpleNamespace(dimension=DIMENSION_BY_VALUE_KIND[kind]), rows, {}
        )
        is False
    )


def test_declared_quote_coordinates_are_not_replaced_by_another_graph_span():
    documents = fields.fixture_documents()
    original = fields.fixture_outputs(documents)["versions"]["candidates"][0]
    rows = declared_rows(
        {"kind": "version_assertion", **original["value"]}, original["evidence"], documents
    )
    rows[0]["block_id"] = str(uuid4())
    service = object.__new__(PublicExtensionReadService)
    service.graph = SimpleNamespace(_load_document=lambda revision, cache: (documents[0], None))
    assert (
        service._claim_has_declared_support(SimpleNamespace(dimension="versions"), rows, {})
        is False
    )
