"""复用独立初审原输入的回归；仅适配本测试schema，不计live或金标。"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from test_t05_persistence_and_raw_store import seed_document

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.sources.nvd import normalize_nvd_page, normalize_nvd_record
from ai_intel.ingestion.sources.vendor_advisories import (
    VendorAdvisoryError,
    normalize_vendor_advisory,
)
from ai_intel.knowledge.models import content_objects, document_revisions, fetch_attempts
from ai_intel.knowledge.revisions import cleanup_unreferenced_object, save_document_revision

WT = Path(__file__).resolve().parents[3]


def nvd_sample():
    return json.loads((WT / "fixtures/recorded/nvd_api_20261015_public.json").read_bytes())


def vendor_sample():
    return json.loads((WT / "fixtures/recorded/vllm_vendor_20261015_public.json").read_bytes())[0]


def test_independent_real_nvd_response_and_all_cvss_versions():
    raw = (WT / "fixtures/recorded/nvd_api_20261015_public.json").read_bytes()
    recorded = nvd_sample()
    original = copy.deepcopy(recorded)
    actual = normalize_nvd_page(recorded)
    assert actual.records[0].cve_id == "CVE-2024-28224"
    assert actual.records[0].metrics[0].score == 6.6
    assert actual.records[0].metrics[0].json_pointer == (
        "/vulnerabilities/0/cve/metrics/cvssMetricV31/0/cvssData/baseScore"
    )
    assert actual.next_start_index == 1 and actual.total_results > 1
    assert recorded == original
    parsed = parse_json_document(raw)
    assert any(
        block.block_type == "field:" + actual.records[0].metrics[0].json_pointer
        for block in parsed.blocks
    )
    variants = {
        "cve": {
            "id": "CVE-2026-12345",
            "metrics": {
                "cvssMetricV2": [
                    {"source": "authority-v2", "cvssData": {"baseScore": 4.0, "version": "2.0"}}
                ],
                "cvssMetricV30": [
                    {"source": "authority-v30", "cvssData": {"baseScore": 5.0, "version": "3.0"}}
                ],
                "cvssMetricV31": [
                    {"source": "authority-v31", "cvssData": {"baseScore": 6.0, "version": "3.1"}}
                ],
                "cvssMetricV40": [
                    {"source": "authority-v40", "cvssData": {"baseScore": 7.0, "version": "4.0"}}
                ],
            },
        }
    }
    normalized = normalize_nvd_record(variants)
    assert [metric.version for metric in normalized.metrics] == ["2.0", "3.0", "3.1", "4.0"]
    assert [metric.score for metric in normalized.metrics] == [4.0, 5.0, 6.0, 7.0]


def test_independent_vendor_real_no_cve_then_cve_and_conditions():
    raw = (WT / "fixtures/recorded/vllm_vendor_20261015_public.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf"
    )
    payload = vendor_sample()
    initial = normalize_vendor_advisory(payload, repository="vllm-project/vllm")
    assert initial.ghsa_id == "GHSA-6cxc-2vcg-w5qc" and initial.cve_id is None
    assert initial.vulnerabilities[0].affected_range == "< 0.31.0"
    assert initial.vulnerabilities[0].patched_version == ">= 0.31.0"
    payload["cve_id"] = "CVE-2026-12345"
    payload["vulnerabilities"][0]["vulnerable_functions"] = ["InputBatch.condense"]
    updated = normalize_vendor_advisory(payload, repository="vllm-project/vllm")
    assert updated.ghsa_id == initial.ghsa_id and updated.canonical_uri == initial.canonical_uri
    assert updated.vulnerabilities[0].vulnerable_functions == ("InputBatch.condense",)
    assert updated.vulnerabilities[0].patched_version == ">= 0.31.0"


@pytest.mark.parametrize("bad", ["invalid\x00text", "invalid\ud800text"])
@pytest.mark.parametrize("field", ["description", "weakness", "reference"])
def test_nvd_invalid_utf8_or_nul_never_becomes_a_normalized_record(field, bad):
    payload = nvd_sample()["vulnerabilities"][0]
    cve = payload["cve"]
    if field == "description":
        cve["descriptions"] = [{"lang": "en", "value": bad}]
    elif field == "weakness":
        cve["weaknesses"] = [{"description": [{"lang": "en", "value": bad}]}]
    else:
        cve["references"] = [{"url": "https://example.invalid/" + bad}]
    with pytest.raises(ValueError):
        normalize_nvd_record(payload)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-15T04:00:00-00:00",
        "2026-10-15T04:00:00+00:60",
        "2026-10-15T04:00:00.1234567Z",
        "2026-10-15T04:00:00+01:00:30",
    ],
)
def test_nvd_unknown_or_invalid_offset_and_lossy_precision_are_not_guessed(timestamp):
    payload = {"cve": {"id": "CVE-2026-12345", "published": timestamp}}
    try:
        normalized = normalize_nvd_record(payload)
    except ValueError:
        return
    assert normalized.published_at is None
    assert normalized.raw_published_at == timestamp


@pytest.mark.parametrize("timestamp", ["2026-10-15T04:00:00-00:00", "2026-10-15T04:00:00.1234567Z"])
def test_vendor_rejects_same_unknown_or_lossy_timestamp(timestamp):
    payload = vendor_sample()
    payload["published_at"] = timestamp
    with pytest.raises(VendorAdvisoryError):
        normalize_vendor_advisory(payload, repository="vllm-project/vllm")


@pytest.mark.parametrize("reference_kind", ["revision", "fetch_attempt"])
def test_new_response_reference_during_gc_never_loses_its_raw_bytes(
    empty_schema_engine, tmp_path, reference_kind
):
    run_migrations(empty_schema_engine.url.render_as_string(hide_password=False))
    store = ContentStore(tmp_path / "objects")
    now = datetime.now(UTC)
    response = store.store_bytes(b'{"vulnerabilities":[{"cve":{"id":"CVE-2026-12345"}}]}')
    with Session(empty_schema_engine) as session, session.begin():
        seed_document(session, "document", "public", None)
        saved = save_document_revision(
            session, store, "document", b'{"cve":{}}', "public", None, now
        )
        session.execute(
            content_objects.insert().values(
                content_hash=response.content_hash, size_bytes=response.size_bytes, created_at=now
            )
        )
        source_id = session.scalar(
            text("SELECT source_id FROM documents WHERE document_id='document'")
        )

    writer_results = []
    writer_done = threading.Event()
    writer_threads = []

    def publish_reference():
        try:
            with Session(empty_schema_engine) as writer, writer.begin():
                if reference_kind == "revision":
                    writer.execute(
                        update(document_revisions)
                        .where(document_revisions.c.revision_id == saved.revision_id)
                        .values(
                            source_response_hash=response.content_hash,
                            source_json_pointer="/vulnerabilities/0",
                        )
                    )
                else:
                    writer.execute(
                        fetch_attempts.insert().values(
                            attempt_id="attempt",
                            source_id=source_id,
                            attempted_at=now,
                            outcome="succeeded",
                            new_event_count=0,
                            response_content_hash=response.content_hash,
                        )
                    )
            writer_results.append("committed")
        except IntegrityError:
            writer_results.append("reference_rejected")
        finally:
            writer_done.set()

    class InterleavedStore:
        """Pause at the observable deletion boundary to finish a concurrent FK writer."""

        def delete_object(self, content_hash):
            thread = threading.Thread(target=publish_reference)
            writer_threads.append(thread)
            thread.start()
            writer_done.wait(timeout=0.5)
            return store.delete_object(content_hash)

    with Session(empty_schema_engine) as collector:
        try:
            with collector.begin():
                cleanup_unreferenced_object(collector, InterleavedStore(), response.content_hash)
        except IntegrityError:
            pass
    for thread in writer_threads:
        thread.join(timeout=8)
        assert not thread.is_alive()
    assert writer_results in (["committed"], ["reference_rejected"])
    if writer_results == ["reference_rejected"]:
        return
    with empty_schema_engine.connect() as connection:
        retained = connection.scalar(
            select(content_objects.c.content_hash).where(
                content_objects.c.content_hash == response.content_hash
            )
        )
        assert retained == response.content_hash
    readable = True
    try:
        store.read_verified(response.content_hash)
    except FileNotFoundError:
        readable = False
    assert readable, "committed response reference points to a PG object whose raw bytes GC deleted"
