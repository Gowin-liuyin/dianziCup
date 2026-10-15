"""Regression inputs preserve missing policy text and unsupported time precision as failures."""

import json
from pathlib import Path

import pytest
from tests.r06_source_worker_fixtures import source_response

from ai_intel.ingestion.catalog_pages import normalize_catalog_page
from ai_intel.ingestion.source_catalog import SourceCatalogError, parse_source_timestamp
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.osv import OsvContractError, normalize_osv_record
from ai_intel.ingestion.sources.repository import RepositoryFetchError

ROOT = Path(__file__).resolve().parents[3]
INVALID_TIMESTAMPS = (
    "2024-01-01T00:00:00+00:99",
    "2024-01-01T00:00:00+24:00",
    "2024-02-30T00:00:00Z",
)
UNKNOWN_INSTANT_TIMESTAMPS = (
    "2024-01-01T00:00:00-00:00",
    "2024-01-01T00:00:00.1234567Z",
    "2024-01-01T00:00:00.123456789Z",
)


def test_real_policy_without_final_effective_sentence_cannot_claim_full_text():
    body = (ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html").read_bytes()
    sentence = "本办法自2023年8月15日起施行。".encode()
    assert body.count(sentence) == 1
    incomplete = body.replace(sentence, b"")
    assert "第二十四条".encode() in incomplete and "施行".encode() in incomplete
    with pytest.raises(SourceCatalogError):
        normalize_catalog_page("cac_generative_ai", incomplete, {})


@pytest.mark.parametrize("timestamp", INVALID_TIMESTAMPS)
def test_generic_time_parser_does_not_normalize_unsupported_source_instant(timestamp):
    with pytest.raises(SourceCatalogError):
        parse_source_timestamp(timestamp)


@pytest.mark.parametrize("field", ["published", "modified", "withdrawn"])
@pytest.mark.parametrize("timestamp", INVALID_TIMESTAMPS)
def test_all_osv_timestamp_fields_validate_before_normalizing(field, timestamp):
    record = json.loads(source_response("osv_ollama")[0])["vulns"][0]
    record[field] = timestamp
    with pytest.raises(OsvContractError):
        normalize_osv_record(record)
    with pytest.raises(OsvContractError):
        normalize_catalog_page("osv_ollama", json.dumps({"vulns": [record]}).encode(), {})


@pytest.mark.parametrize("timestamp", INVALID_TIMESTAMPS)
def test_release_parser_and_catalog_do_not_promote_bad_timestamps(timestamp):
    record = json.loads(source_response("ollama_releases")[0])[0]
    record["published_at"] = timestamp
    body = json.dumps([record]).encode()
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(body)
    with pytest.raises(RepositoryFetchError):
        normalize_catalog_page("ollama_releases", body, {})


@pytest.mark.parametrize("field", ["published", "modified", "withdrawn"])
@pytest.mark.parametrize("timestamp", UNKNOWN_INSTANT_TIMESTAMPS)
def test_osv_preserves_legal_unknown_or_high_precision_time_without_false_utc(field, timestamp):
    assert parse_source_timestamp(timestamp) is None
    record = json.loads(source_response("osv_ollama")[0])["vulns"][0]
    record[field] = timestamp
    normalize_osv_record(record)
    document = normalize_catalog_page(
        "osv_ollama", json.dumps({"vulns": [record]}).encode(), {}
    ).documents[0]
    assert json.loads(document.payload)[field] == timestamp
    if field == "published":
        assert document.published_at is None
        assert document.metadata["published_at_raw"] == timestamp
        assert document.metadata["published_precision"] == "unknown"
    if field == "modified":
        assert document.modified_at is None
        assert document.metadata["modified_at_raw"] == timestamp
    if field == "withdrawn":
        assert document.metadata["withdrawn"] is True


@pytest.mark.parametrize("timestamp", UNKNOWN_INSTANT_TIMESTAMPS)
def test_release_preserves_legal_unknown_time_and_original_precision(timestamp):
    record = json.loads(source_response("ollama_releases")[0])[0]
    record["published_at"] = timestamp
    body = json.dumps([record]).encode()
    assert parse_github_releases(body)[0].published_at == timestamp
    document = normalize_catalog_page("ollama_releases", body, {}).documents[0]
    assert document.published_at is None
    assert document.metadata["published_precision"] == "unknown"
    assert json.loads(document.payload)["published_at"] == timestamp
