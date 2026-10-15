"""Recorded real bytes validate adapters offline, without claiming product live wiring."""

import hashlib
import json
from pathlib import Path

from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.osv import normalize_osv_record

RUN = (
    Path(__file__).resolve().parents[3] / "reports/runs/recovery_r06_repository_community_20261015"
)


def test_actual_ollama_release_retains_identity_and_explicit_timestamp() -> None:
    payload = (RUN / "ollama_release_real.body").read_bytes()
    metadata = json.loads((RUN / "ollama_release_real.metadata.json").read_bytes())
    assert hashlib.sha256(payload).hexdigest() == metadata["body_sha256"]
    records = parse_github_releases(payload)
    assert len(records) == 1
    assert records[0].fixed_identifier == "github:ollama/ollama:release:413093320"
    assert records[0].published_at == "2026-10-14T19:45:22Z"
    assert records[0].record_type == "release"
    assert records[0].title == "v0.40.5"


def test_actual_avid_02_body_is_distinct_from_directory_and_other_record() -> None:
    first = normalize_avid_vulnerability((RUN / "avid_02.record.json").read_bytes())
    second = normalize_avid_vulnerability((RUN / "avid_03.record.json").read_bytes())
    assert first.article_id == "AVID-2023-V001"
    assert second.article_id == "AVID-2023-V002"
    assert first.title == "Evasion of Deep Learning Detector for Malware C&C Traffic"
    assert second.title == "Botnet Domain Generation Algorithm (DGA) Detection Evasion"
    assert first.body_text is not None and "crafted adversarial samples" in first.body_text
    assert second.body_text is not None and "Convolutional Neural Network" in second.body_text
    assert first.referenced_advisory_ids == second.referenced_advisory_ids == ()
    inspection = json.loads((RUN / "avid_record_inspection.json").read_bytes())
    for index, entry in enumerate(inspection, start=2):
        payload = (RUN / f"avid_{index:02}.record.json").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
        assert (
            hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
            == entry["git_blob_sha1"]
        )


def test_actual_osv_keeps_original_nanosecond_precision_and_range_branch() -> None:
    payload = (RUN / "osv_ollama_real.body").read_bytes()
    metadata = json.loads((RUN / "osv_ollama_real.metadata.json").read_bytes())
    assert hashlib.sha256(payload).hexdigest() == metadata["body_sha256"]
    record = normalize_osv_record(json.loads(payload))
    assert record.osv_id == "GHSA-fccc-8m69-8r78"
    assert record.modified_at == "2026-09-10T03:49:48.487641080Z"
    assert record.aliases == ("CVE-2025-0315", "GO-2025-3557")
    assert record.affected[0].package_name == "github.com/ollama/ollama"
    assert record.affected[0].range_branches[0].range_type == "SEMVER"
