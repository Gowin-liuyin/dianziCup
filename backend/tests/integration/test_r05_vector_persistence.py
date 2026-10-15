"""隔离PG验证真实vector类型和增量迁移；这里的合成向量不计模型live。"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, insert, select, text, update
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
from ai_intel.ingestion.source_documents import SourceResponse, persist_source_response
from ai_intel.knowledge.models import document_revisions, evidence
from ai_intel.knowledge.persistence_models import claims, events
from ai_intel.retrieval.persistence_models import retrieval_chunks
from ai_intel.retrieval.service import EventEvidenceRetriever, RetrievalFailure

pytestmark = pytest.mark.real_pg


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
        {"options": f"-c search_path={schema},public -c statement_timeout=15000"}
    )
    connection_url = isolated.render_as_string(hide_password=False)
    engine = create_engine(isolated, connect_args={"connect_timeout": 5})
    try:
        run_migrations(connection_url, "0013_revision_source_metadata")
        fixture = (
            Path(__file__).resolve().parents[3]
            / "fixtures/recorded/vllm_vendor_20261015_public.json"
        )
        record = json.loads(fixture.read_bytes())[0]
        at = datetime(2026, 10, 15, 8, tzinfo=UTC)
        with Session(engine) as session, session.begin():
            persist_source_response(
                session,
                ContentStore(tmp_path_factory.mktemp("vector-content")),
                AccessScope.for_authenticated_user("fixture-vector-admin", None, Role.SYSTEM_ADMIN),
                SourceResponse(
                    "vllm_vendor",
                    json.dumps([record]).encode(),
                    "https://api.github.com/repos/vllm-project/vllm/security-advisories?per_page=10&state=published",
                    at,
                ),
                ingested_at=at,
            )
        with engine.connect() as connection:
            previous = tuple(
                connection.execute(
                    select(evidence.c.evidence_id, evidence.c.quote_sha256).order_by(
                        evidence.c.evidence_id
                    )
                )
            )
        run_migrations(connection_url)
        with engine.connect() as connection:
            following = tuple(
                connection.execute(
                    select(evidence.c.evidence_id, evidence.c.quote_sha256).order_by(
                        evidence.c.evidence_id
                    )
                )
            )
        assert following == previous and following
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
        assert (
            connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
            == "0.8.2"
        )
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0014_grounded_answer_vectors"
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
