"""固定公开来源不能借游标改变外联目标或伪造发布时间。"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from ai_intel.ingestion.source_catalog import (
    CATALOG_SOURCES,
    SourceCatalogError,
    build_catalog_request,
    parse_source_timestamp,
)


@pytest.mark.parametrize("value", ["https://evil.example/", "../main", "a" * 41, "g" * 40])
def test_avid_blob_cursor_cannot_supply_a_url_or_unpinned_ref(value: str) -> None:
    with pytest.raises(SourceCatalogError):
        build_catalog_request("avid_community", {"blob_sha": value})


@pytest.mark.parametrize(
    "cursor", [{"page": True}, {"page": 0}, {"page": 101}, {"url": "https://evil.example"}]
)
def test_repository_paging_requires_bounded_integer_page(cursor: dict[str, object]) -> None:
    with pytest.raises(SourceCatalogError):
        build_catalog_request("ollama_releases", cursor)


def test_osv_package_and_host_cannot_be_overridden_by_cursor() -> None:
    request = build_catalog_request("osv_ollama", {"page_token": "next-token"})
    assert request.method == "POST"
    assert request.url == "https://api.osv.dev/v1/query"
    assert request.json_body == {
        "package": {"ecosystem": "Go", "name": "github.com/ollama/ollama"},
        "page_token": "next-token",
    }
    with pytest.raises(SourceCatalogError):
        build_catalog_request("osv_ollama", {"package": "unapproved"})


def test_source_identity_is_namespaced_and_category_coverage_is_not_alias_counting() -> None:
    assert len({UUID(source.source_id) for source in CATALOG_SOURCES.values()}) == len(
        CATALOG_SOURCES
    )
    assert len({source.category for source in CATALOG_SOURCES.values()}) == 8
    assert CATALOG_SOURCES["nist_ai_rmf"].content_scope == "voluntary_framework"


def test_date_only_and_naive_time_remain_unknown_for_delay_metrics() -> None:
    assert parse_source_timestamp("2023-07-13") is None
    assert parse_source_timestamp("2023-07-13T09:00:00") is None
    assert parse_source_timestamp(None) is None
    assert parse_source_timestamp("2023-07-13T09:00:00+08:00") == datetime(
        2023, 7, 13, 1, tzinfo=UTC
    )


def test_material_document_endpoint_cannot_accept_a_cursor() -> None:
    with pytest.raises(SourceCatalogError):
        build_catalog_request("cac_generative_ai", {"uri": "https://evil.example"})
    assert (
        build_catalog_request("nist_ai_rmf", {}).url
        == "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf"
    )
