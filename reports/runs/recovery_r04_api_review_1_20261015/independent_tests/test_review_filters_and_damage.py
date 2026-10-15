"""Additional root-requested filter and saved-reference shape probes."""

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from ai_intel.api.knowledge_read_service import EventFilters
from ai_intel.enrichment.persistence_models import enrichment_results

from test_api_original_replay import seed_claim, seed_dimension, seed_event, seed_source_document
from test_review_api_boundaries import api_engine, default_pg_client


@pytest.mark.parametrize("field", ["q", "product", "risk_type"])
@pytest.mark.parametrize("invalid_text", ["input\x00NUL", "input\ud800surrogate"])
def test_invalid_unicode_filters_rejected_at_model_boundary(field, invalid_text):
    with pytest.raises(ValidationError):
        EventFilters(**{field:invalid_text})


@pytest.mark.parametrize("column_name", ["source_scope", "claim_ids", "reference_ids"])
def test_corrupt_reference_member_is_fixed_503(api_engine, default_pg_client, column_name):
    revision = seed_source_document(api_engine)
    target = seed_event(api_engine, [revision["revision_id"]])
    claim = seed_claim(api_engine, revision, "review fixture product")
    dimension = seed_dimension(api_engine, target, revision, claim)
    with api_engine.begin() as connection:
        connection.execute(update(enrichment_results).where(enrichment_results.c.result_id == dimension).values(**{column_name:[{}]}))
    response = default_pg_client.get("/v1/events/" + target)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "knowledge_unavailable"
