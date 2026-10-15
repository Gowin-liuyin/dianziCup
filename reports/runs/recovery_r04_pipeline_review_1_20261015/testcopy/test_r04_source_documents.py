"""Recorded source pages against real isolated PG, filesystem and shared services."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.source_documents import (
    SOURCE_DEFINITIONS,
    SourceDocumentError,
    SourceResponse,
    ensure_source_registration,
    persist_source_response,
)
from ai_intel.knowledge.event_linking import EventLinkingError
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    evidence,
    fetch_attempts,
    outbox_events,
    scope_epochs,
    text_blocks,
)
from ai_intel.knowledge.persistence_models import (
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.knowledge.revisions import QuoteConsistencyError

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 5, 15, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("source-test-admin", None, Role.SYSTEM_ADMIN)
FIXTURES = Path('/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review/dianzi/fixtures/recorded')
NVD_URL = (
    "https://services.nvd.nist.gov/rest/json/cves/2.0"
    "?keywordSearch=ollama&resultsPerPage=1&startIndex=0"
)
VENDOR_URL = (
    "https://api.github.com/repos/vllm-project/vllm/security-advisories"
    "?per_page=1&state=published&page=1"
)


@pytest.fixture
def page_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r04_pipeline_review_20261015"
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_r04_source_documents_" + uuid4().hex
    with base.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
        connection.execute(CreateSchema(schema))
    isolated_url = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000"}
    )
    engine = create_engine(isolated_url, connect_args={"connect_timeout": 5})
    run_migrations(isolated_url.render_as_string(hide_password=False))
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def vendor_record():
    return json.loads((FIXTURES / "vllm_vendor_20261015_public.json").read_bytes())[0]


def vendor_response(record=None, observed=NOW):
    body = (
        (FIXTURES / "vllm_vendor_20261015_public.json").read_bytes()
        if record is None
        else (json.dumps([record], ensure_ascii=False, indent=2).encode("utf-8"))
    )
    return SourceResponse("vllm_vendor", body, VENDOR_URL, observed)


def nvd_response(payload=None, observed=NOW):
    body = (
        (FIXTURES / "nvd_api_20261015_public.json").read_bytes()
        if payload is None
        else (json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    )
    return SourceResponse("nvd_ollama", body, NVD_URL, observed)


def persist(engine, store, response, scope=ADMIN):
    with Session(engine) as session, session.begin():
        return persist_source_response(
            session, store, scope, response, ingested_at=response.observed_at + timedelta(seconds=1)
        )


def table_counts(engine):
    with engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (documents, document_revisions, claims, evidence, events, outbox_events)
        )


@pytest.mark.parametrize("source_kind", ["nvd_ollama", "vllm_vendor"])
def test_recorded_source_persists_raw_versions_and_verified_facts(
    page_engine, tmp_path, source_kind
):
    store = ContentStore(tmp_path / "objects")
    response = nvd_response() if source_kind == "nvd_ollama" else vendor_response()
    saved = persist(page_engine, store, response)
    assert saved.new_revision_count == 1 and len(saved.event_ids) == 1
    assert saved.response_content_hash == hashlib.sha256(response.body).hexdigest()
    assert store.read_verified(saved.response_content_hash) == response.body
    with page_engine.connect() as connection:
        revision = connection.execute(select(document_revisions)).mappings().one()
        assert revision["revision_id"] == saved.revision_ids[0]
        assert revision["first_observed_at"] == response.observed_at
        assert revision["ingested_at"] == response.observed_at + timedelta(seconds=1)
        assert revision["parse_status"] == "parsed"
        assert revision["parser_version"] == "json-2.0.0"
        assert revision["normalizer_version"] == "1.0.0"
        raw = store.read_verified(revision["content_hash"])
        assert raw in response.body
        if source_kind == "vllm_vendor":
            assert raw == response.body.strip()[1:-1]
            assert revision["source_json_pointer"] == "/0"
            assert revision["source_published_at"] == datetime(2026, 10, 6, 20, 45, 8, tzinfo=UTC)
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(claims)
                    .where(
                        claims.c.predicate == "affected_product", claims.c.object_value == "vllm"
                    )
                )
                == 1
            )
        else:
            assert revision["source_json_pointer"] == "/vulnerabilities/0"
            assert revision["source_published_at"] is None
            assert revision["source_modified_at"] is None
            score = (
                connection.execute(select(claims).where(claims.c.predicate == "cvss_score"))
                .mappings()
                .one()
            )
            assert score["object_json"]["score"] == 6.6
            assert score["object_json"]["authority"] == "134c704f-9b21-4f2e-91b3-4a467353bcc0"
        attempt = connection.execute(select(fetch_attempts)).mappings().one()
        assert attempt["new_event_count"] == 0
        assert attempt["final_url"] == response.request_url
        assert attempt["attempted_at"] == response.observed_at
        assert attempt["response_content_hash"] == saved.response_content_hash
        for item in connection.execute(select(evidence)).mappings():
            block = (
                connection.execute(
                    select(text_blocks).where(text_blocks.c.block_id == item["block_id"])
                )
                .mappings()
                .one()
            )
            start = item["start_offset"] - block["start_offset"]
            end = item["end_offset"] - block["start_offset"]
            assert block["block_text"][start:end] == item["quote"]
            assert item["quote_sha256"] == hashlib.sha256(item["quote"].encode()).hexdigest()
            assert item["coordinate_version"] == "fulltext_unicode_v1"
            assert item["verified_at"] is not None
            assert block["json_pointer"] == item["locator"] and block["block_type"] == "json_field"
        assert all(
            row[0] == saved.revision_ids[0]
            for row in connection.execute(select(claims.c.source_revision_id))
        )


@pytest.mark.parametrize("source_kind", ["nvd_ollama", "vllm_vendor"])
def test_same_member_reuses_business_records_and_keeps_original_observation(
    page_engine, tmp_path, source_kind
):
    store = ContentStore(tmp_path)
    initial = nvd_response() if source_kind == "nvd_ollama" else vendor_response()
    first = persist(page_engine, store, initial)
    counts = table_counts(page_engine)
    second = persist(
        page_engine,
        store,
        SourceResponse(
            initial.source_kind, initial.body, initial.request_url, NOW + timedelta(minutes=2)
        ),
    )
    assert second.revision_ids == first.revision_ids and second.event_ids == first.event_ids
    assert second.new_revision_count == 0 and table_counts(page_engine) == counts
    with page_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(fetch_attempts)) == 2
        assert connection.scalar(select(document_revisions.c.first_observed_at)) == NOW


def test_envelope_timestamp_only_changes_response_observation(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    original = nvd_response()
    first = persist(page_engine, store, original)
    before = table_counts(page_engine)
    payload = json.loads(original.body)
    old = payload["timestamp"].encode()
    changed_body = original.body.replace(old, b"2099-01-01T00:00:00.000")
    second = persist(
        page_engine,
        store,
        SourceResponse("nvd_ollama", changed_body, NVD_URL, NOW + timedelta(minutes=1)),
    )
    assert second.response_content_hash != first.response_content_hash
    assert second.revision_ids == first.revision_ids and second.new_revision_count == 0
    assert table_counts(page_engine) == before


def test_a_b_a_creates_three_revisions_and_preserves_old_evidence(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    first = persist(page_engine, store, vendor_response())
    modified = vendor_record()
    modified["description"] = "A distinct synthetic source revision with 中文🙂 conditions."
    second = persist(page_engine, store, vendor_response(modified, NOW + timedelta(minutes=1)))
    third = persist(page_engine, store, vendor_response(observed=NOW + timedelta(minutes=2)))
    assert first.event_ids == second.event_ids == third.event_ids
    assert len(set(first.revision_ids + second.revision_ids + third.revision_ids)) == 3
    with page_engine.connect() as connection:
        revisions = (
            connection.execute(
                select(document_revisions).order_by(document_revisions.c.revision_number)
            )
            .mappings()
            .all()
        )
        assert [row["revision_number"] for row in revisions] == [1, 2, 3]
        assert revisions[0]["content_hash"] == revisions[2]["content_hash"]
        assert [row["is_current"] for row in revisions] == [False, False, True]
        assert revisions[1]["previous_revision_id"] == revisions[0]["revision_id"]
        assert revisions[2]["previous_revision_id"] == revisions[1]["revision_id"]
        assert (
            connection.scalar(
                select(func.count())
                .select_from(evidence)
                .where(evidence.c.revision_id == first.revision_ids[0])
            )
            == 2
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(claims)
                .where(
                    claims.c.source_revision_id == first.revision_ids[0],
                    claims.c.is_current.is_(True),
                )
            )
            == 0
        )
        assert store.read_verified(revisions[0]["content_hash"]) in vendor_response().body


def test_non_cve_then_cve_keeps_same_event_id(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    first = persist(page_engine, store, vendor_response())
    modified = vendor_record()
    modified["cve_id"] = "CVE-2026-12345"
    second = persist(page_engine, store, vendor_response(modified, NOW + timedelta(minutes=1)))
    assert second.event_ids == first.event_ids
    with page_engine.connect() as connection:
        identifiers = set(
            connection.execute(select(event_external_ids.c.id_type, event_external_ids.c.id_value))
        )
        assert identifiers == {("ghsa", "GHSA-6CXC-2VCG-W5QC"), ("cve", "CVE-2026-12345")}


def test_existing_external_id_reuses_real_event_identity(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    nvd = persist(page_engine, store, nvd_response())
    vendor = vendor_record()
    vendor["cve_id"] = "CVE-2024-28224"
    saved = persist(page_engine, store, vendor_response(vendor))
    assert saved.event_ids == nvd.event_ids
    with page_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(events)) == 1
        assert (
            connection.scalar(
                select(func.count())
                .select_from(event_documents)
                .where(event_documents.c.active.is_(True))
            )
            == 2
        )


def test_conflicting_external_ids_roll_back_entire_new_page(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    persist(page_engine, store, nvd_response())
    persist(page_engine, store, vendor_response())
    before = table_counts(page_engine)
    vendor = vendor_record()
    vendor["cve_id"] = "CVE-2024-28224"
    with (
        Session(page_engine) as session,
        session.begin(),
        pytest.raises(EventLinkingError, match="conflicting"),
    ):
        persist_source_response(session, store, ADMIN, vendor_response(vendor), ingested_at=NOW)
    assert table_counts(page_engine) == before


def test_caller_rollback_removes_all_facts_and_response_references(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    with Session(page_engine) as session:
        persist_source_response(session, store, ADMIN, vendor_response(), ingested_at=NOW)
        session.rollback()
    assert table_counts(page_engine) == (0, 0, 0, 0, 0, 0)
    with page_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(content_objects)) == 0
        assert connection.scalar(select(func.count()).select_from(fetch_attempts)) == 0


def test_legal_empty_page_records_observation_without_security_conclusion(page_engine, tmp_path):
    saved = persist(
        page_engine, ContentStore(tmp_path), SourceResponse("vllm_vendor", b"[]", VENDOR_URL, NOW)
    )
    assert saved.revision_ids == saved.event_ids == () and saved.new_revision_count == 0
    assert table_counts(page_engine) == (0, 0, 0, 0, 0, 0)
    with page_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(fetch_attempts)) == 1
        assert connection.scalar(select(func.count()).select_from(scope_epochs)) == 0


def test_invalid_member_rolls_back_and_does_not_return_partial_success(page_engine, tmp_path):
    vendor = vendor_record()
    body = json.dumps([vendor, {"unexpected": "structure"}]).encode()
    response = SourceResponse(
        "vllm_vendor", body, VENDOR_URL.replace("per_page=1", "per_page=2"), NOW
    )
    with Session(page_engine) as session, session.begin(), pytest.raises(SourceDocumentError):
        persist_source_response(session, ContentStore(tmp_path), ADMIN, response, ingested_at=NOW)
    assert table_counts(page_engine) == (0, 0, 0, 0, 0, 0)


def test_second_member_storage_failure_rolls_back_first_member_and_fetch_attempt(
    page_engine, tmp_path
):
    first, second = vendor_record(), vendor_record()
    second["ghsa_id"] = "GHSA-2345-6789-cfgh"
    second["html_url"] = (
        "https://github.com/vllm-project/vllm/security/advisories/GHSA-2345-6789-cfgh"
    )
    body = json.dumps([first, second]).encode()

    class FailingMemberStore(ContentStore):
        def store_bytes(self, payload):
            if payload.startswith(b"{") and b"GHSA-2345-6789-cfgh" in payload:
                raise OSError("synthetic isolated member persistence failure")
            return super().store_bytes(payload)

    response = SourceResponse(
        "vllm_vendor", body, VENDOR_URL.replace("per_page=1", "per_page=2"), NOW
    )
    with (
        Session(page_engine) as session,
        session.begin(),
        pytest.raises(OSError, match="isolated member"),
    ):
        persist_source_response(
            session, FailingMemberStore(tmp_path), ADMIN, response, ingested_at=NOW
        )
    assert table_counts(page_engine) == (0, 0, 0, 0, 0, 0)


def test_concurrent_initial_page_only_publishes_once(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        saved = list(pool.map(lambda _: persist(page_engine, store, vendor_response()), range(4)))
    assert sum(item.new_revision_count for item in saved) == 1
    assert len({item.revision_ids for item in saved}) == 1
    with page_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(documents)) == 1
        assert connection.scalar(select(func.count()).select_from(events)) == 1
        assert connection.scalar(select(func.count()).select_from(document_revisions)) == 1
        assert connection.scalar(select(func.count()).select_from(claims)) == 2
        assert connection.scalar(select(func.count()).select_from(fetch_attempts)) == 4


def test_quote_mismatch_is_not_saved_as_supported_fact(page_engine, tmp_path, monkeypatch):
    import ai_intel.ingestion.source_documents as module

    original = module.attach_evidence_span

    def mismatched_quote(*args, **kwargs):
        values = list(args)
        values[5] = "source text that does not occur at this span"
        return original(*values, **kwargs)

    monkeypatch.setattr(module, "attach_evidence_span", mismatched_quote)
    with Session(page_engine) as session, session.begin(), pytest.raises(QuoteConsistencyError):
        persist_source_response(
            session, ContentStore(tmp_path), ADMIN, vendor_response(), ingested_at=NOW
        )
    assert table_counts(page_engine) == (0, 0, 0, 0, 0, 0)


def test_nonpublic_scope_and_malicious_url_cannot_create_source_records(page_engine, tmp_path):
    with Session(page_engine) as session, session.begin():
        with pytest.raises(PermissionDeniedError):
            persist_source_response(
                session,
                ContentStore(tmp_path),
                AccessScope.for_authenticated_user("viewer", "tenant-a", Role.VIEWER),
                vendor_response(),
                ingested_at=NOW,
            )
        with pytest.raises(SourceDocumentError):
            persist_source_response(
                session,
                ContentStore(tmp_path),
                ADMIN,
                SourceResponse("vllm_vendor", b"[]", VENDOR_URL + "&access_token=synthetic", NOW),
                ingested_at=NOW,
            )
    assert table_counts(page_engine) == (0, 0, 0, 0, 0, 0)


def test_existing_registered_source_scope_is_never_overwritten(page_engine, tmp_path):
    with page_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,visibility,"
                "tenant_id,created_at) VALUES (:id,'original-user-source','vendor_advisory',"
                "'https://example.invalid','tenant','tenant-a',:time)"
            ),
            {"id": SOURCE_DEFINITIONS["vllm_vendor"][0], "time": NOW},
        )
    with pytest.raises(SourceDocumentError, match="source identity"):
        persist(page_engine, ContentStore(tmp_path), vendor_response())
    with page_engine.connect() as connection:
        assert connection.execute(text("SELECT name,visibility,tenant_id FROM sources")).one() == (
            "original-user-source",
            "tenant",
            "tenant-a",
        )


@pytest.mark.parametrize("unknown_authority", [False, True])
def test_cvss_unknown_authority_is_pending_and_source_conflict_is_retained(
    page_engine, tmp_path, unknown_authority
):
    payload = json.loads(nvd_response().body)
    metrics = payload["vulnerabilities"][0]["cve"]["metrics"]
    entries = metrics["cvssMetricV31"]
    if unknown_authority:
        entries[0].pop("source", None)
    else:
        second = json.loads(json.dumps(entries[0]))
        second["source"] = "synthetic-second-authority"
        second["cvssData"]["baseScore"] = 8.2
        entries.append(second)
    persist(page_engine, ContentStore(tmp_path), nvd_response(payload))
    with page_engine.connect() as connection:
        dimension = connection.execute(select(enrichment_results)).mappings().one()
        assert dimension["status"] == ("pending" if unknown_authority else "conflict")
        scores = (
            connection.execute(select(claims).where(claims.c.predicate == "cvss_score"))
            .mappings()
            .all()
        )
        assert len(scores) == (0 if unknown_authority else 2)


@pytest.mark.parametrize("mode", ["same_score", "other_version", "unknown_and_known"])
def test_compatible_or_partially_identified_scores_do_not_erase_known_values(
    page_engine, tmp_path, mode
):
    payload = json.loads(nvd_response().body)
    metrics = payload["vulnerabilities"][0]["cve"]["metrics"]
    duplicate = json.loads(json.dumps(metrics["cvssMetricV31"][0]))
    duplicate["source"] = "synthetic-second-authority"
    if mode == "same_score":
        metrics["cvssMetricV31"].append(duplicate)
    elif mode == "other_version":
        duplicate["cvssData"]["version"] = "2.0"
        duplicate["cvssData"]["vectorString"] = "AV:N/AC:L/Au:N/C:P/I:P/A:P"
        duplicate["cvssData"]["baseScore"] = 4.0
        metrics["cvssMetricV2"] = [duplicate]
    else:
        duplicate.pop("source")
        metrics["cvssMetricV31"].append(duplicate)
    persist(page_engine, ContentStore(tmp_path), nvd_response(payload))
    with page_engine.connect() as connection:
        assert connection.scalar(select(enrichment_results.c.status)) == "available"
        assert connection.scalar(
            select(func.count()).select_from(claims).where(claims.c.predicate == "cvss_score")
        ) == (1 if mode == "unknown_and_known" else 2)


def test_source_registration_is_reusable_without_creating_documents(page_engine):
    with Session(page_engine) as session, session.begin():
        first = ensure_source_registration(session, ADMIN, "vllm_vendor", NOW)
        second = ensure_source_registration(
            session, ADMIN, "vllm_vendor", NOW + timedelta(minutes=1)
        )
        assert first == second == SOURCE_DEFINITIONS["vllm_vendor"][0]
    assert table_counts(page_engine) == (0, 0, 0, 0, 0, 0)
    with page_engine.connect() as connection:
        assert connection.execute(
            text("SELECT name,category,base_origin,visibility,tenant_id,created_at FROM sources")
        ).one() == (
            "vLLM repository security advisories",
            "vendor_advisory",
            "https://api.github.com",
            "public",
            None,
            NOW,
        )


def test_score_authority_and_vector_have_independent_exact_evidence(page_engine, tmp_path):
    persist(page_engine, ContentStore(tmp_path), nvd_response())
    with page_engine.connect() as connection:
        score_id = connection.scalar(
            select(claims.c.claim_id).where(claims.c.predicate == "cvss_score")
        )
        paths = set(
            connection.scalars(
                select(evidence.c.locator)
                .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
                .where(claim_evidence.c.claim_id == score_id)
            )
        )
        assert paths == {
            "/cve/metrics/cvssMetricV31/0/cvssData/baseScore",
            "/cve/metrics/cvssMetricV31/0/cvssData/vectorString",
            "/cve/metrics/cvssMetricV31/0/source",
        }


def test_rejected_and_withdrawn_source_declarations_are_explicit_facts(page_engine, tmp_path):
    store = ContentStore(tmp_path)
    payload = json.loads(nvd_response().body)
    payload["vulnerabilities"][0]["cve"]["vulnStatus"] = "Rejected"
    persist(page_engine, store, nvd_response(payload))
    vendor = vendor_record()
    vendor["withdrawn_at"] = "2026-10-07T20:45:08Z"
    persist(page_engine, store, vendor_response(vendor))
    with page_engine.connect() as connection:
        declared = set(
            connection.execute(
                select(claims.c.predicate, claims.c.object_value, claims.c.claim_origin).where(
                    claims.c.predicate.in_(("source_status", "source_withdrawn_at"))
                )
            )
        )
        assert declared == {
            ("source_status", "Rejected", "source_explicit"),
            ("source_withdrawn_at", "2026-10-07T20:45:08Z", "source_explicit"),
        }
