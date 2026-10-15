"""A stored workflow retains readable rule/context provenance, not only an opaque hash."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r07_enrichment_publication_pg import inputs, publish

from ai_intel.knowledge.persistence_models import change_events

pytestmark = pytest.mark.real_pg


def test_parent_publication_persists_the_exact_rule_and_event_context(catalog_engine, tmp_path):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    request_id = uuid4()
    results = publish(catalog_engine, loaded, attempts, request_id)
    with Session(catalog_engine) as session:
        row = (
            session.execute(
                select(change_events).where(
                    change_events.c.change_type == "enrichment_attempts_published"
                )
            )
            .mappings()
            .one()
        )
    assert row["payload"]["schema_version"] == 2
    assert row["payload"]["context"] == loaded.context.model_dump(mode="json")
    assert row["payload"]["context"]["rule_version"] == "fixture-publish-1"
    assert (
        row["payload"]["context"]["expected_event_version"] == loaded.context.expected_event_version
    )
    assert str(loaded.context.event_id) in row["entity_ids"]
    assert len(results) == 4
