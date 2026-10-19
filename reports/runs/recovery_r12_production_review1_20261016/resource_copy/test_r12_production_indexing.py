"""Reuse unchanged T30 behaviors on production 0020, without ad hoc table creation."""

import os
from collections.abc import Iterator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.integration import test_t30_hybrid_retrieval as original
from tests.r12_hybrid_fixtures import FixtureSemanticModels

from ai_intel.infrastructure.database import run_migrations
from ai_intel.retrieval.hybrid import HybridRetriever
from ai_intel.retrieval.hybrid_contracts import IndexGeneration
from ai_intel.retrieval.indexing import HybridIndexer
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient

pytestmark = pytest.mark.real_pg

for original_name in dir(original):
    if original_name.startswith("test_"):
        globals()[original_name] = getattr(original, original_name)


@pytest.fixture()
def corpus(
    isolated_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Engine, HybridIndexer, HybridRetriever]]:
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r12_prod_review1_20261016"
    assert url.host == "127.0.0.1" and url.port == 25432
    schema = "test_r12_production_" + uuid4().hex
    base = create_engine(url, hide_parameters=True)
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    configured = url.update_query_dict(
        {"options": f"-c search_path={schema},public -c statement_timeout=15000"}
    )
    migration_url = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000"}
    )
    engine = create_engine(configured, hide_parameters=True)

    def forbidden_create_all(*arguments, **keywords):
        raise AssertionError("production indexing must use forward migrations")

    monkeypatch.setattr(MetaData, "create_all", forbidden_create_all)
    client = None
    generation = IndexGeneration("r12-" + uuid4().hex, "dianzi_test_r12_" + uuid4().hex)
    try:
        run_migrations(migration_url.render_as_string(hide_password=False))
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0020_hybrid_retrieval"
            )
        assert set(inspect(engine).get_table_names(schema=schema)).issuperset(
            {
                "hybrid_chunks",
                "hybrid_index_generations",
                "hybrid_index_watermarks",
                "hybrid_index_receipts",
            }
        )
        client = httpx.Client(base_url=os.environ["R12_OPENSEARCH_URL"], timeout=10.0)
        search = OpenSearchCorpusClient(client)
        models = FixtureSemanticModels()
        indexer = HybridIndexer(engine, models, search, generation)
        indexer.prepare_generation()
        yield engine, indexer, HybridRetriever(engine, models, search, generation)
    finally:
        if client is not None:
            assert generation.index_name.startswith("dianzi_test_r12_")
            response = client.delete("/" + generation.index_name)
            assert response.status_code in {200, 404}
            client.close()
        engine.dispose()
        assert schema.startswith("test_r12_production_") and schema.isidentifier()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()
