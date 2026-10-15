"""隔离PG验证真实vector类型和增量迁移；这里的合成向量不计模型live。"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import DateTime, MetaData, Table, create_engine, func, insert, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.models.clients import EmbeddingResult
from ai_intel.infrastructure.models.semantic import (
    E5_MODEL,
    RERANK_MODEL,
    RankedPassage,
    RerankResult,
)
from ai_intel.knowledge.models import document_revisions, evidence
from ai_intel.knowledge.persistence_models import claims, events
from ai_intel.retrieval.persistence_models import retrieval_chunks
from ai_intel.retrieval.service import EventEvidenceRetriever, RetrievalFailure

pytestmark = pytest.mark.real_pg

LEGACY_SEED_TABLES = (
    "sources",
    "content_objects",
    "documents",
    "document_revisions",
    "text_blocks",
    "evidence",
    "events",
    "event_external_ids",
    "event_documents",
    "claims",
    "claim_assertions",
    "claim_evidence",
    "claim_status_history",
    "scope_epochs",
    "change_events",
    "job_runs",
    "outbox_events",
    "publication_receipts",
    "fetch_attempts",
)


def load_legacy_0013_seed(engine: Engine, schema: str, store: ContentStore) -> tuple[Table, ...]:
    """Load the frozen old writer output using only the migrated 0013 column definitions."""
    assert schema.startswith("test_r05_") and schema.isidentifier()
    recorded = Path(__file__).resolve().parents[3] / "fixtures/recorded"
    seed_bytes = (
        (recorded / "r05_legacy_0013_vllm_public_v1.json").read_bytes().replace(b"\r\n", b"\n")
    )
    assert hashlib.sha256(seed_bytes).hexdigest() == (
        "6170ce55e63a70a557f62fc79213d20b596222220e2a04d5e050e67b7e188336"
    )
    seed = json.loads(seed_bytes)
    assert seed["fixture_version"] == 1 and seed["data_mode"] == "fixture"
    assert seed["migration_revision"] == "0013_revision_source_metadata"
    assert seed["writer_commit"] == "1927eeb00a7e0c1335f76340b0382f46102f08f2"
    source_bytes = (recorded / "vllm_vendor_20261015_public.json").read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == seed["source_fixture_sha256"]
    original_body = json.dumps([json.loads(source_bytes)[0]]).encode()
    assert hashlib.sha256(original_body).hexdigest() == seed["response_body_sha256"]
    assert set(seed["required_tables"]) == set(LEGACY_SEED_TABLES) == set(seed["tables"])
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0013_revision_source_metadata"
        )
        prepared = []
        for name in LEGACY_SEED_TABLES:
            table = Table(
                name, MetaData(), schema=schema, autoload_with=connection, resolve_fks=False
            )
            table_seed = seed["tables"][name]
            assert set(table_seed["columns"]) == set(table.columns.keys())
            assert table_seed["rows"]
            assert connection.scalar(select(func.count()).select_from(table)) == 0
            for row in table_seed["rows"]:
                assert set(row) == set(table_seed["columns"])
                for column in table.columns:
                    if isinstance(column.type, DateTime) and row[column.name] is not None:
                        value = datetime.fromisoformat(row[column.name])
                        assert value.tzinfo is not None and value.utcoffset() is not None
                        row[column.name] = value.astimezone(UTC)
                if "visibility" in row:
                    assert row["visibility"] == "public" and row["tenant_id"] is None
                if "tenant_id" in row:
                    assert row["tenant_id"] is None
                if "scope_key" in row:
                    assert row["scope_key"] == "public"
            prepared.append((table, table_seed["rows"]))
        content_rows = seed["tables"]["content_objects"]["rows"]
        assert set(seed["content_payloads_utf8"]) == {row["content_hash"] for row in content_rows}
        for row in content_rows:
            payload = seed["content_payloads_utf8"][row["content_hash"]].encode("utf-8")
            assert hashlib.sha256(payload).hexdigest() == row["content_hash"]
            assert len(payload) == row["size_bytes"]
            assert store.store_bytes(payload).content_hash == row["content_hash"]
            assert store.read_verified(row["content_hash"]) == payload
        for table, rows in prepared:
            if table.name == "claim_status_history":
                inserted = connection.scalars(
                    insert(table).returning(table.c.transition_sequence),
                    [
                        {key: value for key, value in row.items() if key != "transition_sequence"}
                        for row in rows
                    ],
                ).all()
                assert inserted == [row["transition_sequence"] for row in rows]
            else:
                connection.execute(insert(table), rows)
    return tuple(table for table, _rows in prepared)


@pytest.fixture
def vector_database(isolated_test_database_url: str, tmp_path_factory: pytest.TempPathFactory):
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r05_pgvector_20261015"
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_r05_vectors_" + uuid4().hex
    with base.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000"}
    )
    connection_url = isolated.render_as_string(hide_password=False)
    runtime_url = isolated.update_query_dict(
        {"options": f"-c search_path={schema},public -c statement_timeout=15000"}
    )
    engine = create_engine(runtime_url, connect_args={"connect_timeout": 5})
    try:
        run_migrations(connection_url, "0013_revision_source_metadata")
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text(
                        "SELECT n.nspname FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE c.oid=to_regclass('alembic_version')"
                    )
                )
                == schema
            )
        store = ContentStore(tmp_path_factory.mktemp("vector-content"))
        legacy_tables = load_legacy_0013_seed(engine, schema, store)
        with engine.connect() as connection:
            previous_seed = tuple(
                tuple(connection.execute(select(table).order_by(*table.primary_key.columns)))
                for table in legacy_tables
            )
            previous = tuple(
                connection.execute(
                    select(evidence.c.evidence_id, evidence.c.quote_sha256).order_by(
                        evidence.c.evidence_id
                    )
                )
            )
        run_migrations(connection_url)
        with engine.connect() as connection:
            following_seed = tuple(
                tuple(connection.execute(select(table).order_by(*table.primary_key.columns)))
                for table in legacy_tables
            )
            following = tuple(
                connection.execute(
                    select(evidence.c.evidence_id, evidence.c.quote_sha256).order_by(
                        evidence.c.evidence_id
                    )
                )
            )
        assert following == previous and following
        assert following_seed == previous_seed
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def chunk_values(
    session: Session, coordinate: float, space: str = "fixture-space-v1"
) -> dict[str, object]:
    row = session.execute(select(evidence.c.evidence_id, evidence.c.revision_id).limit(1)).one()
    vector = [0.0] * 384
    vector[0] = coordinate
    vector[1] = 1.0
    return {
        "chunk_id": str(uuid4()),
        "evidence_id": row.evidence_id,
        "revision_id": row.revision_id,
        "start_offset": 0,
        "end_offset": 4,
        "chunk_text": "test",
        "text_sha256": "0" * 64,
        "model_version": space,
        "embedding": vector,
        "indexed_at": datetime.now(UTC),
    }


def test_upgrade_preserves_immutable_evidence_and_real_extension(vector_database: Engine) -> None:
    with vector_database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(document_revisions)) == 1
        assert connection.scalar(select(document_revisions.c.source_metadata)) == {}
        assert (
            connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
            == "0.8.2"
        )
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0015_catalog_document_metadata"
        )


def test_real_vector_roundtrip_cosine_and_model_space_filter(vector_database: Engine) -> None:
    with Session(vector_database) as session:
        first = chunk_values(session, 1.0)
        second = chunk_values(session, -1.0, "fixture-space-v2")
        session.execute(insert(retrieval_chunks), [first, second])
        query = [1.0, 1.0] + [0.0] * 382
        distance = retrieval_chunks.c.embedding.cosine_distance(query)
        rows = session.execute(
            select(retrieval_chunks.c.chunk_id, distance.label("distance"))
            .where(retrieval_chunks.c.model_version == "fixture-space-v1")
            .order_by(distance)
        ).all()
        assert [row.chunk_id for row in rows] == [first["chunk_id"]]
        assert rows[0].distance == pytest.approx(0.0, abs=1e-6)
        roundtrip = session.scalar(
            select(retrieval_chunks.c.embedding).where(
                retrieval_chunks.c.chunk_id == first["chunk_id"]
            )
        )
        assert roundtrip == [1.0, 1.0] + [0.0] * 382


@pytest.mark.parametrize("invalid", [[1.0] * 383, [float("nan")] * 384, [float("inf")] * 384])
def test_real_pg_rejects_bad_dimensions_and_nonfinite_values(
    vector_database: Engine, invalid: list[float]
) -> None:
    with Session(vector_database) as session:
        values = chunk_values(session, 1.0)
        values["embedding"] = invalid
        with pytest.raises(DBAPIError):
            session.execute(insert(retrieval_chunks).values(values))
        session.rollback()
        assert session.scalar(select(func.count()).select_from(retrieval_chunks)) == 0


def test_chunk_coordinates_are_not_permanent_evidence_coordinates(vector_database: Engine) -> None:
    with Session(vector_database) as session:
        values = chunk_values(session, 1.0)
        values["end_offset"] = 5
        with pytest.raises(IntegrityError):
            session.execute(insert(retrieval_chunks).values(values))


class FixtureSemanticModels:
    """仅用于PG接线合同，固定向量不计语义模型或召回率证据。"""

    def __init__(self) -> None:
        self.passage_calls = 0

    def embed_query(self, query: str) -> EmbeddingResult:
        return EmbeddingResult(((1.0,) + (0.0,) * 383,), E5_MODEL.model_version, 384)

    def embed_passages(self, passages: tuple[str, ...]) -> EmbeddingResult:
        self.passage_calls += 1
        return EmbeddingResult(
            tuple((1.0,) + (0.0,) * 383 for _ in passages), E5_MODEL.model_version, 384
        )

    def rerank(self, query: str, passages: tuple[str, ...]) -> RerankResult:
        return RerankResult(
            tuple(RankedPassage(index, float(-index)) for index in range(len(passages))),
            RERANK_MODEL.model_version,
        )


def public_event_id(engine: Engine) -> UUID:
    with engine.connect() as connection:
        return UUID(connection.scalar(select(events.c.event_id)))


def test_event_retrieval_reuses_real_pg_vectors_and_exact_evidence(vector_database: Engine) -> None:
    models = FixtureSemanticModels()
    scope = AccessScope.for_authenticated_user("fixture-analyst", "test-tenant", Role.ANALYST)
    retriever = EventEvidenceRetriever(vector_database, models)
    result = retriever.retrieve(scope, public_event_id(vector_database), "请给出原文风险")
    assert result.citations and result.embedding_model == E5_MODEL.model_version
    with Session(vector_database) as session:
        assert session.scalar(select(func.count()).select_from(retrieval_chunks)) > 0
        for citation in result.citations:
            quote = session.scalar(
                select(evidence.c.quote).where(evidence.c.evidence_id == str(citation.evidence_id))
            )
            assert citation.quote in quote
    calls = models.passage_calls
    repeated = retriever.retrieve(scope, public_event_id(vector_database), "同一事件的修复信息")
    assert models.passage_calls == calls
    assert repeated.citations


def test_private_event_is_rejected_before_model_or_index(vector_database: Engine) -> None:
    event_id = public_event_id(vector_database)
    with vector_database.begin() as connection:
        connection.execute(
            update(events).values(
                visibility="tenant", tenant_id="tenant-private", scope_key="tenant:tenant-private"
            )
        )
    models = FixtureSemanticModels()
    retriever = EventEvidenceRetriever(vector_database, models)
    with pytest.raises(CrossTenantAccessError):
        retriever.retrieve(
            AccessScope.for_authenticated_user("other", "tenant-other", Role.ANALYST),
            event_id,
            "风险",
        )
    assert models.passage_calls == 0


def test_removing_only_current_revision_cannot_generate_a_fact(vector_database: Engine) -> None:
    with vector_database.begin() as connection:
        connection.execute(update(document_revisions).values(is_current=False))
    models = FixtureSemanticModels()
    with pytest.raises(RetrievalFailure, match="answer_evidence_unavailable"):
        EventEvidenceRetriever(vector_database, models).retrieve(
            AccessScope.for_authenticated_user("reader", "tenant", Role.VIEWER),
            public_event_id(vector_database),
            "风险",
        )
    assert models.passage_calls == 0


def test_corrupt_derived_chunk_is_rejected_instead_of_cited(vector_database: Engine) -> None:
    models = FixtureSemanticModels()
    scope = AccessScope.for_authenticated_user("fixture-reader", "tenant", Role.VIEWER)
    retriever = EventEvidenceRetriever(vector_database, models)
    event_id = public_event_id(vector_database)
    retriever.retrieve(scope, event_id, "风险")
    with vector_database.begin() as connection:
        connection.execute(update(retrieval_chunks).values(text_sha256="f" * 64))
    with pytest.raises(RetrievalFailure, match="answer_index_integrity_unavailable"):
        retriever.retrieve(scope, event_id, "风险")


def test_withdrawn_claims_cannot_be_resurrected_from_old_source_quotes(
    vector_database: Engine,
) -> None:
    with vector_database.begin() as connection:
        before = connection.scalar(select(func.count()).select_from(evidence))
        connection.execute(update(claims).values(claim_status="withdrawn"))
    models = FixtureSemanticModels()
    with pytest.raises(RetrievalFailure, match="answer_evidence_unavailable"):
        EventEvidenceRetriever(vector_database, models).retrieve(
            AccessScope.for_authenticated_user("reader", "tenant", Role.VIEWER),
            public_event_id(vector_database),
            "风险",
        )
    with vector_database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(evidence)) == before
    assert models.passage_calls == 0
