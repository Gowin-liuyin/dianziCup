"""Independent real PG checks use synthetic bytes in a dedicated test database."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_r07_input_capabilities_pg import ADMIN, PUBLIC, seed_catalogue

from ai_intel.api.document_read_service import sources
from ai_intel.enrichment.taxonomy_inputs import TaxonomyInputError, load_taxonomy_catalogue
from ai_intel.knowledge.models import content_objects, document_revisions, documents

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize("parent", ["source", "document", "revision"])
def test_all_parent_changes_block_while_loader_transaction_holds_share(migrated_engine, tmp_path, parent):
    store, revision, source, document = seed_catalogue(migrated_engine, tmp_path)
    table, column, identity, values = {
        "source": (sources, sources.c.source_id, source, {"visibility": "tenant", "tenant_id": "review-owner"}),
        "document": (documents, documents.c.document_id, document, {"visibility": "tenant", "tenant_id": "review-owner"}),
        "revision": (document_revisions, document_revisions.c.revision_id, str(revision), {"is_current": False}),
    }[parent]

    def mutate():
        with migrated_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='150ms'"))
            with pytest.raises(OperationalError) as failure:
                connection.execute(update(table).where(column == identity).values(**values))
            assert failure.value.orig.sqlstate == "55P03"

    with Session(migrated_engine) as session, session.begin():
        result = load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")
        assert result.supported_ids == {"CWE-79", "CWE-89"}
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(mutate).result(timeout=10)


@pytest.mark.parametrize("failure", ["missing", "unavailable"])
def test_object_failures_are_distinct_and_never_empty_success(migrated_engine, tmp_path, failure):
    _, revision, _, _ = seed_catalogue(migrated_engine, tmp_path)

    class FailedStore:
        def read_verified(self, digest):
            if failure == "missing":
                raise FileNotFoundError("synthetic missing")
            raise OSError("synthetic unavailable")

    with Session(migrated_engine) as session, pytest.raises(TaxonomyInputError, match="taxonomy_object_" + failure):
        load_taxonomy_catalogue(session, FailedStore(), ADMIN, PUBLIC, revision, "cwe")


def test_pg_object_size_mismatch_is_integrity_error(migrated_engine, tmp_path):
    store, revision, _, _ = seed_catalogue(migrated_engine, tmp_path)
    with Session(migrated_engine) as session:
        digest = session.scalar(select(document_revisions.c.content_hash).where(document_revisions.c.revision_id == str(revision)))
    with migrated_engine.begin() as connection:
        connection.execute(update(content_objects).where(content_objects.c.content_hash == digest).values(size_bytes=400))
    try:
        with Session(migrated_engine) as session, pytest.raises(TaxonomyInputError, match="taxonomy_object_integrity_invalid"):
            load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(update(content_objects).where(content_objects.c.content_hash == digest).values(size_bytes=len(store.read_verified(digest))))


def test_malformed_saved_uri_returns_typed_error(migrated_engine, tmp_path):
    store, revision, _, _ = seed_catalogue(migrated_engine, tmp_path)
    with migrated_engine.begin() as connection:
        connection.execute(update(document_revisions).where(document_revisions.c.revision_id == str(revision)).values(canonical_uri="https://cwe.mitre.org:bad/data/xml/cwec_v4.19.xml"))
    with Session(migrated_engine) as session, pytest.raises(TaxonomyInputError, match="taxonomy_source_uri_invalid"):
        load_taxonomy_catalogue(session, store, ADMIN, PUBLIC, revision, "cwe")
