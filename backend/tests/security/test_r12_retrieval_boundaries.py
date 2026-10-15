"""Trust boundaries for the independent internal corpus interface."""

import json

import httpx
import pytest

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.retrieval.hybrid import authorized_scope_keys, facts_query
from ai_intel.retrieval.hybrid_contracts import HybridQuery, IndexGeneration
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient, bm25_body


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.invalid:9200",
        "https://user:secret@search.invalid",
        "https://search.invalid/path",
        "https://search.invalid?secret=1",
        "https://search.invalid#fragment",
    ],
)
def test_search_client_rejects_untrusted_connection_shapes(url: str) -> None:
    with httpx.Client(base_url=url) as client, pytest.raises(ValueError):
        OpenSearchCorpusClient(client)


@pytest.mark.parametrize(
    "name", ["*", "_all", "other_index", "dianzi_../../_search", "dianzi_*", "dianzi_a/b"]
)
def test_index_cannot_escape_dedicated_namespace(name: str) -> None:
    with pytest.raises(ValueError):
        OpenSearchCorpusClient._index(IndexGeneration("fixture-generation", name))


def test_viewer_scope_never_adds_private_search_filter() -> None:
    scope = AccessScope.for_authenticated_user("server-user", "tenant-a", Role.VIEWER)
    assert authorized_scope_keys(scope) == ("public",)
    body = json.dumps(
        bm25_body(
            IndexGeneration("fixture", "dianzi_test_r12_scope"),
            scope,
            HybridQuery("tenant-b OR *:*", include_graph=False),
        )
    )
    assert '"term": {"tenant_id"' not in body
    assert '"query_string"' not in body


def test_permissions_are_checked_before_querying() -> None:
    with pytest.raises(PermissionDeniedError):
        authorized_scope_keys(AccessScope("server-user", "tenant-a", Role.ANALYST))


def test_pg_fact_query_filters_each_authority_before_returning_rows() -> None:
    scope = AccessScope.for_authenticated_user("server-user", "tenant-a", Role.ANALYST)
    sql = str(facts_query(scope, HybridQuery("risk")).compile())
    for relation in ("events", "evidence", "document_revisions", "documents", "sources", "claims"):
        assert relation + ".visibility" in sql
        assert relation + ".tenant_id" in sql
    assert "document_revisions.is_current" in sql
    assert "claim_evidence.validation_status" in sql
