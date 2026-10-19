"""Recorded NVD bytes are local contract inputs, not a live source observation."""

from datetime import UTC, datetime

from tests.r06_source_worker_fixtures import source_response

from ai_intel.ingestion.source_documents import SourceResponse, _prepare_documents


def test_recorded_nvd_payload_is_bytes_at_publication_boundary() -> None:
    body, content_type = source_response("nvd_ollama")
    assert isinstance(body, bytes)
    assert content_type == "application/json"
    response = SourceResponse(
        "nvd_ollama",
        body,
        "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=100&startIndex=0",
        datetime(2026, 10, 17, tzinfo=UTC),
        data_mode="fixture",
    )
    assert _prepare_documents(response)
