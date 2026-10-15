"""Workflow requests carry business choices, never tenant identity or model credentials."""

import pytest
from pydantic import ValidationError

from ai_intel.enrichment.job_contracts import (
    ALL_ENRICHMENT_DIMENSIONS,
    EventEnrichmentRequest,
)


def test_default_request_preserves_all_nine_dimensions():
    request = EventEnrichmentRequest.model_validate_json('{"expected_event_version":1}')
    assert request.dimensions == ALL_ENRICHMENT_DIMENSIONS
    assert len(request.dimensions) == 9
    assert request.product_query_id is None


def test_dimension_order_is_canonical_but_selection_is_not_expanded():
    request = EventEnrichmentRequest.model_validate_json(
        '{"expected_event_version":4,"dimensions":["versions","cvss"]}'
    )
    assert request.dimensions == ("cvss", "versions")
    assert request.expected_event_version == 4


@pytest.mark.parametrize("dimension", ALL_ENRICHMENT_DIMENSIONS)
def test_every_dimension_has_an_independent_request(dimension):
    request = EventEnrichmentRequest.model_validate_json(
        '{"expected_event_version":1,"dimensions":["' + dimension + '"]}'
    )
    assert request.dimensions == (dimension,)


@pytest.mark.parametrize(
    "body",
    [
        '{"expected_event_version":true}',
        '{"expected_event_version":0}',
        '{"expected_event_version":"1"}',
        '{"expected_event_version":1,"dimensions":[]}',
        '{"expected_event_version":1,"dimensions":["cvss","cvss"]}',
        '{"expected_event_version":1,"dimensions":["made_up"]}',
        '{"expected_event_version":1,"dimensions":"atlas"}',
        '{"expected_event_version":1,"dimensions":[null]}',
        '{"expected_event_version":1,"tenant_id":"self_reported"}',
        '{"expected_event_version":1,"role":"system_admin"}',
        '{"expected_event_version":1,"api_key":"untrusted_request_field"}',
        '{"expected_event_version":1,"model":"arbitrary_provider_model"}',
        '{"expected_event_version":1,"product_query_id":"arbitrary_product"}',
        '{"expected_event_version":1,"dimensions":["atlas"],"product_query_id":"ollama"}',
    ],
)
def test_invalid_or_authority_bearing_requests_are_rejected(body):
    with pytest.raises(ValidationError):
        EventEnrichmentRequest.model_validate_json(body)


@pytest.mark.parametrize("query_id", ["ollama", "vllm"])
def test_aggregate_product_choices_are_closed_and_separate_from_asset_scope(query_id):
    request = EventEnrichmentRequest.model_validate_json(
        '{"expected_event_version":1,"dimensions":["exposure"],"product_query_id":"'
        + query_id
        + '"}'
    )
    assert request.product_query_id == query_id
    assert request.dimensions == ("exposure",)
