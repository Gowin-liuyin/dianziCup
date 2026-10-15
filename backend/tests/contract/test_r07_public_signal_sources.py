"""Explicit synthetic wire cases do not establish a live publisher connection."""

import io
import json
import zipfile

import pytest

from ai_intel.enrichment.signal_sources import (
    PublicSignalError,
    build_public_signal_request,
    select_cwe_catalog_document,
    select_public_signal_document,
)

CVE = "CVE-2024-37032"


def epss_body(**changes: object) -> bytes:
    return json.dumps(
        {
            "status": "OK",
            "status-code": 200,
            "version": "1.0",
            "total": 1,
            "offset": 0,
            "limit": 100,
            "data": [{"cve": CVE, "epss": "0.0", "percentile": "0.1", "date": "2026-10-14"}],
            **changes,
        }
    ).encode()


def test_fixed_request_and_true_zero_are_preserved():
    request = build_public_signal_request("epss", CVE)
    assert request.url == "https://api.first.org/data/v1/epss?cve=CVE-2024-37032"
    document = select_public_signal_document("epss", epss_body(), CVE)
    payload = json.loads(document.payload)
    assert payload["response"]["data"][0]["epss"] == "0.0"
    assert "model_version" not in payload["response"]
    assert payload["selection"]["source_record_index"] == 0


@pytest.mark.parametrize("cve", ["", "CVE-2024-1", CVE + "&q=x", "cve-2024-37032"])
def test_request_rejects_non_closed_query(cve):
    with pytest.raises(PublicSignalError):
        build_public_signal_request("epss", cve)


@pytest.mark.parametrize(
    "changes",
    [
        {"status-code": True},
        {"status": "ERROR"},
        {"offset": 1},
        {"total": 2},
        {"data": []},
        {"data": [{"cve": "CVE-2024-12345", "epss": "0", "percentile": "0", "date": "2026-10-14"}]},
    ],
)
def test_malformed_or_cross_cve_response_is_not_a_zero(changes):
    with pytest.raises(PublicSignalError):
        select_public_signal_document("epss", epss_body(**changes), CVE)


def test_absent_epss_requires_complete_empty_lookup():
    document = select_public_signal_document("epss", epss_body(total=0, data=[]), CVE)
    assert json.loads(document.payload)["selection"]["complete_response"] is True


def kev_body(**changes: object) -> bytes:
    return json.dumps(
        {
            "catalogVersion": "2026.10.15",
            "dateReleased": "2026-10-15T19:00:00Z",
            "count": 1,
            "vulnerabilities": [
                {
                    "cveID": CVE,
                    "dateAdded": "2026-09-01",
                    "requiredAction": "Apply updates.",
                    "dueDate": "2026-09-22",
                    "knownRansomwareCampaignUse": "Unknown",
                }
            ],
            **changes,
        }
    ).encode()


@pytest.mark.parametrize(
    "field,bad",
    [
        ("epss", True),
        ("epss", "NaN"),
        ("epss", "1.00001"),
        ("epss", -0.1),
        ("epss", None),
        ("percentile", "Infinity"),
        ("percentile", "0e0"),
        ("date", "20261014"),
        ("date", "2026-02-30"),
        ("date", None),
    ],
)
def test_epss_invalid_probability_or_date_fails(field, bad):
    payload = json.loads(epss_body())
    payload["data"][0][field] = bad
    with pytest.raises(PublicSignalError):
        select_public_signal_document("epss", json.dumps(payload).encode(), CVE)


def test_duplicate_epss_rows_and_duplicate_json_keys_fail():
    payload = json.loads(epss_body())
    payload["data"] *= 2
    payload["total"] = 2
    with pytest.raises(PublicSignalError):
        select_public_signal_document("epss", json.dumps(payload).encode(), CVE)
    with pytest.raises(PublicSignalError, match="invalid_signal_json"):
        select_public_signal_document("epss", b'{"status":"OK","status":"ERROR"}', CVE)


def test_kev_selection_keeps_original_scope_and_not_found():
    present = select_public_signal_document("kev", kev_body(), CVE)
    payload = json.loads(present.payload)
    assert payload["response"]["vulnerabilities"][0]["requiredAction"] == "Apply updates."
    assert payload["selection"]["source_total_count"] == 1
    assert payload["selection"]["query_scope"] == "complete_catalog"
    absent = select_public_signal_document("kev", kev_body(), "CVE-2024-12345")
    assert json.loads(absent.payload)["response"]["vulnerabilities"] == []
    assert json.loads(absent.payload)["selection"]["source_record_index"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"count": 2},
        {"count": True},
        {"catalogVersion": None},
        {"dateReleased": "2026-10-15"},
        {"dateReleased": "2026-10-15T19:00:00+00:99"},
        {"vulnerabilities": None},
    ],
)
def test_invalid_or_partial_kev_cannot_establish_absence(changes):
    with pytest.raises(PublicSignalError):
        select_public_signal_document("kev", kev_body(**changes), "CVE-2024-12345")


@pytest.mark.parametrize(
    "field,bad",
    [
        ("cveID", "CVE-2024-1"),
        ("requiredAction", ""),
        ("dueDate", "2026-02-30"),
        ("dateAdded", None),
        ("knownRansomwareCampaignUse", "False"),
        ("knownRansomwareCampaignUse", {}),
    ],
)
def test_invalid_unselected_kev_row_also_fails_catalog(field, bad):
    payload = json.loads(kev_body())
    payload["vulnerabilities"][0][field] = bad
    with pytest.raises(PublicSignalError):
        select_public_signal_document("kev", json.dumps(payload).encode(), "CVE-2024-12345")


def test_duplicate_kev_cve_is_not_silently_selected():
    payload = json.loads(kev_body())
    payload["vulnerabilities"] *= 2
    payload["count"] = 2
    with pytest.raises(PublicSignalError, match="duplicate_kev_cve"):
        select_public_signal_document("kev", json.dumps(payload).encode(), CVE)


def cwe_xml(body="", version="0.1"):
    return (
        f'<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-7" Version="{version}">'
        f"<Weaknesses>{body}</Weaknesses></Weakness_Catalog>"
    ).encode()


def test_cwe_selection_keeps_complete_catalog_count_and_missing_ids():
    raw = cwe_xml(
        '<Weakness ID="78" Name="Command Injection"/>'
        '<Weakness ID="79" Name="Cross-site Scripting"/>'
    )
    member = select_cwe_catalog_document(raw, ("CWE-78", "CWE-999999"))
    payload = json.loads(member.payload)
    assert payload["taxonomy_version"] == "0.1"
    assert payload["selection"]["total_weaknesses"] == 2
    assert len(payload["weaknesses"]) == 1
    assert payload["missing_cwe_ids"] == ["CWE-999999"]
    assert "royalty-free license" in payload["license"]
    assert "The MITRE Corporation" in payload["copyright"]


@pytest.mark.parametrize(
    "raw",
    [
        b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///secret">]><x>&x;</x>',
        b"<x/>",
        cwe_xml('<Weakness ID="78" Name="A"/><Weakness ID="78" Name="B"/>'),
        cwe_xml('<Weakness ID="0" Name="A"/>'),
        cwe_xml('<Weakness ID="78" Name=""/>'),
        cwe_xml('<Weakness ID="78" Name="A"/>', ""),
        cwe_xml(),
    ],
)
def test_cwe_catalog_rejects_entities_wrong_root_duplicates_or_incomplete_metadata(raw):
    with pytest.raises(PublicSignalError):
        select_cwe_catalog_document(raw, ("CWE-78",))


@pytest.mark.parametrize("name", ["../cwec.xml", "C:/cwec.xml", "nested/cwec.xml", "wrong.txt"])
def test_cwe_zip_path_is_never_extracted(name):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(name, cwe_xml('<Weakness ID="78" Name="A"/>'))
    with pytest.raises(PublicSignalError, match="invalid_cwe_archive"):
        select_cwe_catalog_document(stream.getvalue(), ("CWE-78",))


def test_zip_positive_and_compression_bomb_rejection():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cwec_v0.1.xml", cwe_xml('<Weakness ID="78" Name="A"/>'))
    assert select_cwe_catalog_document(stream.getvalue(), ("CWE-78",)).kind.value == "standard"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cwec.xml", b"A" * 1000000)
    with pytest.raises(PublicSignalError, match="invalid_cwe_archive"):
        select_cwe_catalog_document(stream.getvalue(), ("CWE-78",))
