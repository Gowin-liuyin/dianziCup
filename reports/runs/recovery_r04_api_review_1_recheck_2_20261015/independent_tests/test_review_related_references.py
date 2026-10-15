"""A saved public reference to a different event is damage, not an ACL-hidden input."""

import pytest
from sqlalchemy import update

from ai_intel.enrichment.persistence_models import enrichment_results
from test_api_original_replay import seed_claim, seed_dimension, seed_event, seed_source_document
from test_review_api_boundaries import api_engine, default_pg_client


@pytest.mark.parametrize("column_name", ["claim_ids", "reference_ids"])
def test_existing_public_unrelated_reference_is_not_successful_empty_dimension(api_engine, default_pg_client, column_name):
    original = seed_source_document(api_engine)
    unrelated = seed_source_document(api_engine, body="unrelated public document")
    target = seed_event(api_engine, [original["revision_id"]])
    unrelated_event = seed_event(api_engine, [unrelated["revision_id"]])
    original_claim = seed_claim(api_engine, original, "original public product")
    unrelated_claim = seed_claim(api_engine, unrelated, "unrelated public product")
    dimension = seed_dimension(api_engine, target, original, original_claim)
    assert default_pg_client.get("/v1/events/" + unrelated_event).status_code == 200
    assert default_pg_client.get("/v1/evidence/" + unrelated["evidence_id"]).status_code == 200
    identifier = unrelated_claim if column_name == "claim_ids" else unrelated["evidence_id"]
    with api_engine.begin() as connection:
        connection.execute(update(enrichment_results).where(enrichment_results.c.result_id == dimension).values(**{column_name:[identifier]}))
    response = default_pg_client.get("/v1/events/" + target)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "knowledge_unavailable"
