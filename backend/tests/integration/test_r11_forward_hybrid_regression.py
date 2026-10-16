"""Unchanged R12 22 behavior functions use production 0022 and owned search indexes."""

import os
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import MetaData, Table
from sqlalchemy.engine import make_url
from tests.integration import test_r12_production_indexing as original
from tests.r11_forward_fixtures import forbid_metadata_creation, migrated_schema
from tests.r12_hybrid_fixtures import FixtureSemanticModels

from ai_intel.retrieval.hybrid import HybridRetriever
from ai_intel.retrieval.hybrid_contracts import IndexGeneration
from ai_intel.retrieval.indexing import HybridIndexer
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient

pytestmark = pytest.mark.real_pg

for original_name in dir(original):
    if original_name.startswith("test_"):
        globals()[original_name] = getattr(original, original_name)


@pytest.fixture()
def corpus(monkeypatch, register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(make_url(os.environ["TEST_DATABASE_URL"]).password))
    search_url = os.environ["R12_OPENSEARCH_URL"]
    parsed = urlsplit(search_url)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 29200
    assert parsed.username is None and parsed.password is None
    generation = IndexGeneration(
        "r11-forward-" + uuid4().hex, "dianzi_test_r11_forward_" + uuid4().hex
    )
    with migrated_schema() as (engine, _url, _schema):
        monkeypatch.setattr(MetaData, "create_all", forbid_metadata_creation)
        monkeypatch.setattr(Table, "create", forbid_metadata_creation)
        with httpx.Client(base_url=search_url, timeout=10.0) as client:
            search = OpenSearchCorpusClient(client)
            models = FixtureSemanticModels()
            indexer = HybridIndexer(engine, models, search, generation)
            try:
                indexer.prepare_generation()
                yield engine, indexer, HybridRetriever(engine, models, search, generation)
            finally:
                assert generation.index_name.startswith("dianzi_test_r11_forward_")
                response = client.delete("/" + generation.index_name)
                assert response.status_code in {200, 404}
