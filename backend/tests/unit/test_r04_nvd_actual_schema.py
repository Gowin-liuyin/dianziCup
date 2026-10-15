"""真实NVD留档样本与明确隔离负例，不计live/正式金标或持续监测。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.sources.nvd import (
    NvdUnavailableError,
    fetch_with_rate_limit_guard,
    normalize_nvd_page,
    normalize_nvd_record,
)
from ai_intel.knowledge.evidence import locate_evidence_span

SAMPLE = Path(__file__).resolve().parents[3] / "fixtures/recorded/nvd_api_20261015_public.json"


def sample() -> dict[str, object]:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_real_api_20_wrapper_nested_cvss_authority_vector_and_pointer() -> None:
    record = normalize_nvd_page(sample()).records[0]
    assert record.cve_id == "CVE-2024-28224"
    assert record.weaknesses == ("CWE-346",)
    assert record.scores == (("cvssMetricV31", 6.6),)
    metric = record.metrics[0]
    assert metric.authority == "134c704f-9b21-4f2e-91b3-4a467353bcc0"
    assert metric.vector == "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:H"
    assert len(record.references) == 3
    outcome = parse_json_document(SAMPLE.read_bytes())
    block = next(
        block for block in outcome.blocks if block.block_type == "field:" + metric.json_pointer
    )
    span = locate_evidence_span(outcome.blocks, "6.6", block_id=block.block_id)
    assert outcome.normalized_text[span.start_offset : span.end_offset] == "6.6"
    assert normalize_nvd_page(sample()).next_start_index == 1


def test_cvss_conflicting_authorities_and_absent_source_are_not_overwritten() -> None:
    item = {
        "cve": {
            "id": "CVE-2026-12345",
            "metrics": {
                "cvssMetricV31": [
                    {"source": "authority-a", "cvssData": {"baseScore": 7.5}},
                    {"source": "authority-b", "cvssData": {"baseScore": 9.8}},
                    {"cvssData": {"baseScore": 4.1}},
                ]
            },
        }
    }
    record = normalize_nvd_record(item)
    assert [metric.score for metric in record.metrics] == [7.5, 9.8, 4.1]
    assert [metric.authority for metric in record.metrics] == ["authority-a", "authority-b", None]


@pytest.mark.parametrize("invalid", [True, -1, 10.1, float("inf"), float("nan"), "7.5"])
def test_invalid_or_boolean_cvss_is_not_silently_a_score(invalid: object) -> None:
    with pytest.raises(ValueError, match="score"):
        normalize_nvd_record(
            {
                "cve": {
                    "id": "CVE-2026-12345",
                    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": invalid}}]},
                }
            }
        )


def test_missing_fields_and_rejected_status_are_explicit_not_zero_scores() -> None:
    record = normalize_nvd_record({"cve": {"id": "CVE-2026-12345", "vulnStatus": "Rejected"}})
    assert record.description is None and record.published_at is None
    assert record.scores == record.metrics == ()
    assert record.status == "Rejected"


@pytest.mark.parametrize(
    "payload",
    [
        {"vulnerability": {"cve": {"id": "CVE-2026-12345"}}},
        {"cve": {"id": "CVE-２０２６-12345"}},
        {"cve": {"id": "CVE-2026-12345", "metrics": {"cvssMetricV31": [{"baseScore": 8}]}}},
    ],
)
def test_fake_legacy_wrapper_or_score_path_and_non_ascii_ids_are_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        normalize_nvd_record(payload)


def test_empty_intermediate_page_cannot_silently_advance_past_missing_results() -> None:
    page = {
        "format": "NVD_CVE",
        "version": "2.0",
        "startIndex": 0,
        "totalResults": 5,
        "resultsPerPage": 0,
        "vulnerabilities": [],
    }
    with pytest.raises(ValueError, match="incomplete"):
        normalize_nvd_page(page)
    page["totalResults"] = 0
    assert normalize_nvd_page(page).next_start_index is None


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_http_failure_is_called_once_and_handed_to_task_retry(status: int) -> None:
    calls: list[int] = []

    def request() -> dict[str, object]:
        calls.append(status)
        return {"status_code": status}

    with pytest.raises(NvdUnavailableError) as failed:
        fetch_with_rate_limit_guard(request)
    assert failed.value.status_code == status
    assert calls == [status]


def test_naive_source_times_preserve_raw_values_without_guessing_a_timezone() -> None:
    record = normalize_nvd_page(sample()).records[0]
    assert record.published_at is None and record.last_modified_at is None
    assert record.raw_published_at == "2024-04-08T19:15:07.353"
    assert record.raw_last_modified_at == "2026-06-17T07:21:12.873"


def test_explicit_source_offsets_are_converted_to_utc_and_original_kept() -> None:
    record = normalize_nvd_record(
        {
            "cve": {
                "id": "CVE-2026-12345",
                "published": "2026-10-15T12:00:00+08:00",
                "lastModified": "2026-10-15T05:00:00Z",
            }
        }
    )
    assert record.published_at == "2026-10-15T04:00:00+00:00"
    assert record.last_modified_at == "2026-10-15T05:00:00+00:00"
    assert record.raw_published_at == "2026-10-15T12:00:00+08:00"


@pytest.mark.parametrize("value", ["yesterday", "2026-10-15", "2026-02-30T00:00:00Z"])
def test_invalid_source_timestamps_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        normalize_nvd_record({"cve": {"id": "CVE-2026-12345", "published": value}})
