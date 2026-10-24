"""Real worker documents feed bounded immutable enrichment inputs without leaking scope."""

from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from tests.integration.test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from tests.integration.test_r06_source_worker_pg import handler_for, queue, run

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.enrichment.inputs import EnrichmentInputError, load_event_enrichment_inputs
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import content_objects, document_revisions, text_blocks
from ai_intel.knowledge.persistence_models import event_external_ids, events

ADMIN = AccessScope.for_authenticated_user("enrichment-fixture", None, Role.SYSTEM_ADMIN)
pytestmark = pytest.mark.real_pg


def seeded_event(engine, tmp_path, kind="nvd_ollama"):
    store = ContentStore(tmp_path)
    job_id = queue(engine, kind)
    assert run(engine, job_id, handler_for(store, kind, data_mode="fixture")) in {
        "succeeded",
        "partial",
    }
    with Session(engine) as session:
        event_id = session.scalar(select(events.c.event_id))
    return store, UUID(event_id)


@pytest.mark.parametrize("kind", ["nvd_ollama", "vllm_vendor"])
def test_actual_worker_pg_and_raw_objects_supply_visible_fixed_revision_inputs(
    catalog_engine, tmp_path, kind
):
    store, event_id = seeded_event(catalog_engine, tmp_path, kind)
    with Session(catalog_engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, event_id, "r07-fixture-1")
        assert loaded.context.event_id == event_id
        assert loaded.context.expected_event_version == 1
        assert len(loaded.documents) == len(loaded.context.revision_ids) == 1
        document = loaded.documents[0]
        assert document.json_payload == store.read_verified(document.content_sha256)
        assert document.revision_id in loaded.context.revision_ids
        assert document.blocks_complete and document.content_coverage == "full_text"
        assert len(loaded.context.external_cve_ids) == (1 if kind == "nvd_ollama" else 0)
        assert loaded.scope.visibility == "public"
        assert all(block.text_sha256 and block.json_pointer for block in document.blocks)


def test_scope_denied_before_object_store_is_read(catalog_engine, tmp_path):
    _store, event_id = seeded_event(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(update(events).values(visibility="tenant", tenant_id="fixture-owner"))
    outsider = AccessScope.for_authenticated_user("other", "fixture-other", Role.TENANT_ADMIN)

    class UnreadableStore:
        def read_verified(self, digest, *, deadline_monotonic=None):
            pytest.fail("out-of-scope object IO must not happen")

    with Session(catalog_engine) as session, pytest.raises(CrossTenantAccessError):
        load_event_enrichment_inputs(session, UnreadableStore(), outsider, event_id, "rule")


@pytest.mark.parametrize("state", ["merged", "withdrawn"])
def test_non_active_event_cannot_feed_new_enrichment(catalog_engine, tmp_path, state):
    store, event_id = seeded_event(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(update(events).values(status=state))
    with Session(catalog_engine) as session, pytest.raises(EnrichmentInputError):
        load_event_enrichment_inputs(session, store, ADMIN, event_id, "rule")


def test_old_source_revision_is_rejected_instead_of_silent_current_input(catalog_engine, tmp_path):
    store, event_id = seeded_event(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(update(document_revisions).values(is_current=False))
    with Session(catalog_engine) as session, pytest.raises(EnrichmentInputError):
        load_event_enrichment_inputs(session, store, ADMIN, event_id, "rule")


def test_corrupt_raw_content_cannot_become_an_empty_signal_search(catalog_engine, tmp_path):
    store, event_id = seeded_event(catalog_engine, tmp_path)
    with Session(catalog_engine) as session:
        digest = session.scalar(select(document_revisions.c.content_hash))
    store.object_path_for_hash(digest).write_bytes(b"corrupted synthetic content")
    with Session(catalog_engine) as session, pytest.raises(EnrichmentInputError):
        load_event_enrichment_inputs(session, store, ADMIN, event_id, "rule")


def test_corrupt_saved_block_hash_cannot_publish_source_supported_values(catalog_engine, tmp_path):
    store, event_id = seeded_event(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(update(text_blocks).values(text_sha256="0" * 64))
    with Session(catalog_engine) as session, pytest.raises(EnrichmentInputError):
        load_event_enrichment_inputs(session, store, ADMIN, event_id, "rule")


def test_event_cve_requires_an_explicit_bound_source_field(catalog_engine, tmp_path):
    store, event_id = seeded_event(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(update(event_external_ids).values(id_value="CVE-2026-9999999"))
    with Session(catalog_engine) as session, pytest.raises(EnrichmentInputError):
        load_event_enrichment_inputs(session, store, ADMIN, event_id, "rule")


def test_content_budget_is_checked_before_object_io(catalog_engine, tmp_path):
    _store, event_id = seeded_event(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(update(content_objects).values(size_bytes=2 * 1024 * 1024 + 1))

    class UnreadableStore:
        def read_verified(self, digest, *, deadline_monotonic=None):
            pytest.fail("over-budget object IO must not happen")

    with Session(catalog_engine) as session, pytest.raises(EnrichmentInputError):
        load_event_enrichment_inputs(session, UnreadableStore(), ADMIN, event_id, "rule")


def test_partial_blocks_remain_incomplete_without_becoming_full_text(catalog_engine, tmp_path):
    store, event_id = seeded_event(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(update(document_revisions).values(parse_status="partial"))
    with Session(catalog_engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, event_id, "rule")
        assert not loaded.documents[0].blocks_complete


def test_lying_store_is_rechecked_against_pg_content_identity(catalog_engine, tmp_path):
    _store, event_id = seeded_event(catalog_engine, tmp_path)

    class LyingStore:
        def read_verified(self, digest, *, deadline_monotonic=None):
            return b"not the saved synthetic content"

    with Session(catalog_engine) as session, pytest.raises(EnrichmentInputError):
        load_event_enrichment_inputs(session, LyingStore(), ADMIN, event_id, "rule")
