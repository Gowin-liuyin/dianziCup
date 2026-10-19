"""Real isolated PG and immutable object storage; taxonomy bytes and transport are synthetic."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from tests.unit.test_r07_input_capabilities import CWE_XML

from ai_intel.api.document_read_service import sources
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.inputs import EnrichmentInputError, load_event_enrichment_inputs
from ai_intel.enrichment.model_fields import extract_model_dimension
from ai_intel.enrichment.taxonomy_inputs import TaxonomyInputError, load_taxonomy_catalogue
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import document_revisions, documents, text_blocks
from ai_intel.knowledge.revisions import register_response_content, save_document_revision

pytestmark = pytest.mark.real_pg
ADMIN = AccessScope.for_authenticated_user("fixture-loader", None, Role.SYSTEM_ADMIN)
PUBLIC = VisibilityScope(visibility="public")
NOW = datetime(2026, 10, 16, tzinfo=UTC)


def seed_catalogue(engine, tmp_path):
    store = ContentStore(tmp_path)
    source_id, document_id = str(uuid4()), str(uuid4())
    with Session(engine) as session, session.begin():
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES(:id,:name,'technical_standard','https://cwe.mitre.org',"
                "'public',NULL,:time)"
            ),
            {"id": source_id, "name": "synthetic CWE fixture " + source_id, "time": NOW},
        )
        stored = register_response_content(session, store, CWE_XML, NOW)
        session.execute(
            insert(documents).values(
                document_id=document_id,
                source_id=source_id,
                kind="standard",
                title="Synthetic CWE",
                retrieved_at=NOW,
                content_hash=stored.content_hash,
                visibility="public",
                schema_version=1,
            )
        )
        saved = save_document_revision(
            session,
            store,
            document_id,
            CWE_XML,
            "public",
            None,
            NOW,
            revision_metadata={"content_coverage": "full_text", "taxonomy_version": "4.19"},
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == saved.revision_id)
            .values(
                canonical_uri="https://cwe.mitre.org/data/xml/cwec_v4.19.xml", parse_status="parsed"
            )
        )
    return store, UUID(saved.revision_id), source_id, document_id


def test_current_catalogue_is_hash_bound_and_replayable_from_pg(migrated_engine, tmp_path):
    store, revision, source, document = seed_catalogue(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        first = load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")
        replay = load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")
        assert first == replay
        assert first.supported_ids == {"CWE-79", "CWE-89"}
        assert first.provenance.revision_id == revision
        assert first.provenance.document_id == UUID(document)
        assert first.provenance.source_id == UUID(source)


@pytest.mark.parametrize("parent", ["source", "document", "revision"])
def test_each_private_parent_is_denied_before_object_read(migrated_engine, tmp_path, parent):
    _store, revision, source, document = seed_catalogue(migrated_engine, tmp_path)
    table, column, key = {
        "source": (sources, sources.c.source_id, source),
        "document": (documents, documents.c.document_id, document),
        "revision": (document_revisions, document_revisions.c.revision_id, str(revision)),
    }[parent]
    with migrated_engine.begin() as connection:
        connection.execute(
            update(table).where(column == key).values(visibility="tenant", tenant_id="owner")
        )

    class NoReadStore:
        def read_verified(self, digest):
            pytest.fail("invisible catalogue caused object IO")

    with Session(migrated_engine) as session, pytest.raises(EnrichmentInputError):
        load_taxonomy_catalogue(session, NoReadStore(), ADMIN, PUBLIC, revision, "cwe")


def test_permissionless_context_is_rejected_before_pg_or_objects(migrated_engine, tmp_path):
    store, revision, _, _ = seed_catalogue(migrated_engine, tmp_path)
    denied = AccessScope("fixture-denied", None, Role.SYSTEM_ADMIN)
    with Session(migrated_engine) as session, pytest.raises(PermissionDeniedError):
        load_taxonomy_catalogue(session, store, denied, PUBLIC, revision, "cwe")


@pytest.mark.parametrize("mutation", ["stale", "partial", "version", "uri"])
def test_saved_catalogue_state_does_not_silently_become_supported_ids(
    migrated_engine, tmp_path, mutation
):
    store, revision, _, _ = seed_catalogue(migrated_engine, tmp_path)
    values = {
        "stale": {"is_current": False},
        "partial": {"source_metadata": {"content_coverage": "excerpt", "taxonomy_version": "4.19"}},
        "version": {
            "source_metadata": {"content_coverage": "full_text", "taxonomy_version": "4.18"}
        },
        "uri": {"canonical_uri": "https://example.invalid/fake-cwe.xml"},
    }[mutation]
    with migrated_engine.begin() as connection:
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == str(revision))
            .values(**values)
        )
    with Session(migrated_engine) as session, pytest.raises(TaxonomyInputError):
        load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")


def test_source_acl_is_locked_during_catalogue_read(migrated_engine, tmp_path):
    store, revision, source, _ = seed_catalogue(migrated_engine, tmp_path)

    def attempt_acl_change():
        with migrated_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='150ms'"))
            with pytest.raises(OperationalError) as failure:
                connection.execute(
                    update(sources)
                    .where(sources.c.source_id == source)
                    .values(visibility="tenant", tenant_id="owner")
                )
            assert failure.value.orig.sqlstate == "55P03"

    with Session(migrated_engine) as session, session.begin():
        catalogue = load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(attempt_acl_change).result(timeout=10)
        assert catalogue.supported_ids == {"CWE-79", "CWE-89"}
    with Session(migrated_engine) as session:
        assert (
            session.scalar(select(sources.c.visibility).where(sources.c.source_id == source))
            == "public"
        )


def test_corrupt_stored_catalogue_is_not_an_empty_id_set(migrated_engine, tmp_path):
    store, revision, _, _ = seed_catalogue(migrated_engine, tmp_path)
    with Session(migrated_engine) as session:
        digest = session.scalar(
            select(document_revisions.c.content_hash).where(
                document_revisions.c.revision_id == str(revision)
            )
        )
    store.object_path_for_hash(digest).write_bytes(b"corrupted synthetic catalogue")
    with (
        Session(migrated_engine) as session,
        pytest.raises(TaxonomyInputError, match="taxonomy_object_integrity_invalid"),
    ):
        load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")


def test_retained_nvd67_blocks_supply_bounded_model_input_without_changing_pg_source(
    migrated_engine, tmp_path, monkeypatch
):
    from test_r07_enrichment_inputs_pg import seeded_event
    from tests.unit.test_r07_single_model_dimension import prepared_transport

    store, event_id = seeded_event(migrated_engine, tmp_path)
    with Session(migrated_engine) as session:
        loaded = load_event_enrichment_inputs(
            session, store, ADMIN, event_id, "synthetic-r07-inputs-1"
        )
        document = loaded.documents[0]
        original = document.model_dump_json()
        assert len(document.blocks) == 67
        raw = store.read_verified(document.content_sha256)
        client, calls = prepared_transport(monkeypatch, outputs={"versions": {"candidates": []}})
        result = extract_model_dimension(
            loaded.context,
            loaded.documents,
            client,
            dimension="versions",
            budget_authorized=True,
            content_is_private=False,
            egress_granted=False,
        )
        assert len(calls) == 1
        assert calls[0][1]["max_completion_tokens"] == 1024
        assert result.attempts[0].error_code == "field_evidence_missing"
        assert result.input_selections[0].incomplete
        assert 0 < len(result.input_selections[0].selected) < 67
        assert document.model_dump_json() == original
        assert store.read_verified(document.content_sha256) == raw
        rows = tuple(
            session.scalars(
                select(text_blocks.c.block_id).where(
                    text_blocks.c.revision_id == str(document.revision_id)
                )
            )
        )
        assert set(rows) == {str(block.block_id) for block in document.blocks}
