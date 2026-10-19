"""Synthetic context-image boundary cases; no source image is fetched or copied."""

import json

import pytest

from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.repository import RepositoryFetchError


def synthetic_record(reference_uri, reference_type="screenshot"):
    return json.dumps({
        "data_type": "AVID", "data_version": "0.2",
        "metadata": {"vuln_id": "AVID-2026-V999"},
        "problemtype": {"description": {"lang": "en", "value": "Synthetic title"}},
        "description": {"lang": "en", "value": "Synthetic context body"},
        "references": [{"type": reference_type, "label": "Synthetic image", "url": reference_uri}],
    }).encode()


def test_known_repository_image_reference_is_context_without_advisory_identity():
    record = normalize_avid_vulnerability(synthetic_record("../img/R00031.png"))
    assert record.article_id == "AVID-2026-V999"
    assert record.referenced_advisory_ids == ()
    assert record.body_text == "Synthetic context body"


@pytest.mark.parametrize("uri", [
    "../../img/R00031.png", "../img/../R00031.png", "../img/R00031.png?token=synthetic",
    "../img/R00031.png#fragment", "../img/R00031.png\n", "..\\img\\R00031.png",
    "../img/%52%30%30%30%33%31.png", "file:///img/R00031.png",
    "http://127.0.0.1/R00031.png", "https://example.com:8443/R00031.png",
    "https://user:synthetic@example.com/R00031.png", "../img/R00031.exe",
])
def test_unknown_or_unsafe_reference_is_still_quarantined(uri):
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(synthetic_record(uri))


def test_relative_image_shape_with_unsupported_type_is_still_quarantined():
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(synthetic_record("../img/R00031.png", "website"))
