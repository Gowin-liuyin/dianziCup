"""隔离PG验证真实vector类型和增量迁移；这里的合成向量不计模型live。"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.source_documents import SourceResponse, persist_source_response
from ai_intel.knowledge.models import document_revisions, evidence
from ai_intel.retrieval.persistence_models import retrieval_chunks

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
