"""Owned real-PG cases with synthetic source bytes; Root provisions nonce/OID-fenced resources."""

import hashlib
import json
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, insert, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from tests.integration import test_r11_pg_assessments as original
from tests.unit.test_public_write_adapters import fixture_request
from tests.unit.test_r07_public_signals import CVE, nvd_payload

from ai_intel.api.auth_state import auth_sessions, lock_authenticated_scope
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.api.public_risk_summary import build_current_stack_envelope
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier
from ai_intel.enrichment.inputs import load_event_enrichment_inputs
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.knowledge.models import document_revisions, documents
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import event_documents, event_external_ids
from ai_intel.knowledge.revisions import (
    SourceRevisionBlock,
    attach_evidence_span,
    register_response_content,
    register_source_revision_blocks,
    save_document_revision,
)

pytestmark = pytest.mark.real_pg
STAMP = datetime(2026, 10, 17, tzinfo=UTC)


@pytest.fixture()
def pg_engine(register_sensitive_failure_value) -> Iterator[Engine]:
    run_id = os.environ["DIANZI_TEST_RUN_ID"]
    assert re.fullmatch(r"r18_current_risk_[a-z0-9_]{8,80}", run_id)
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.password
    register_sensitive_failure_value(SecretStr(url.password))
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, "test_dianzi_" + run_id)
    assert url.username and url.username.startswith("test_")
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
        assert connection.scalar(text("SELECT current_user")) == url.username
        assert str(connection.scalar(text("SELECT current_schema()"))).startswith("test_r18_risk_")
        identity = connection.execute(
            text(
                "SELECT oid, shobj_description(oid, 'pg_authid') AS comment "
                "FROM pg_roles WHERE rolname = :name"
            ),
            {"name": url.username},
        ).one()
        assert identity.oid == int(os.environ["DIANZI_TEST_ROLE_OID"])
        assert identity.comment == os.environ["DIANZI_TEST_ROLE_COMMENT"]
        database = connection.execute(
            text(
                "SELECT oid, shobj_description(oid, 'pg_database') AS comment "
                "FROM pg_database WHERE datname = current_database()"
            )
        ).one()
        assert database.oid == int(os.environ["DIANZI_TEST_DATABASE_OID"])
        assert database.comment == os.environ["DIANZI_TEST_DATABASE_COMMENT"]
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0030_revalidation_actor_bindings"
        )
    try:
        yield engine
    finally:
        engine.dispose()


def prepare_fixture_source_inputs(session, seeded):
    """Register readable fixture rule bytes and a public catalog-bound CVE owner only.

    The separate tenant Grade source retains the original ACL oracle. The registered owner
    contains no score and cannot add a CVSS candidate or change the requested freshness.
    """
    session.execute(
        update(document_revisions)
        .where(document_revisions.c.revision_id == seeded["revision_id"])
        .values(
            canonical_uri="https://example.invalid/r18-fixture/rule/" + seeded["document_id"],
            source_metadata={"data_mode": "fixture", "content_coverage": "full_text"},
        )
    )
    catalog = CATALOG_SOURCES["nvd_ollama"]
    session.execute(
        text(
            "INSERT INTO sources(source_id,name,category,base_origin,visibility,tenant_id,"
            "created_at) VALUES (:id,'Synthetic registered NVD owner',:category,:origin,"
            "'public',NULL,:stamp) ON CONFLICT (source_id) DO NOTHING"
        ),
        {
            "id": catalog.source_id,
            "category": catalog.category.value,
            "origin": catalog.base_origin,
            "stamp": STAMP,
        },
    )
    body = json.dumps({"cve": {"id": CVE}}).encode()
    parsed = parse_json_document(body)
    document_id = str(uuid4())
    content = register_response_content(session, seeded["store"], body, STAMP)
    session.execute(
        insert(documents).values(
            document_id=document_id,
            source_id=catalog.source_id,
            kind="advisory",
            title="Synthetic CVE owner only",
            retrieved_at=STAMP,
            content_hash=content.content_hash,
            visibility="public",
            tenant_id=None,
            schema_version=2,
        )
    )
    revision = save_document_revision(
        session,
        seeded["store"],
        document_id,
        body,
        "public",
        None,
        STAMP,
        revision_metadata={"data_mode": "fixture", "content_coverage": "full_text"},
    )
    session.execute(
        update(document_revisions)
        .where(document_revisions.c.revision_id == revision.revision_id)
        .values(
            parse_status="parsed",
            canonical_uri="https://nvd.nist.gov/vuln/detail/" + CVE,
            first_observed_at=STAMP,
        )
    )
    register_source_revision_blocks(
        session,
        revision.revision_id,
        tuple(
            SourceRevisionBlock(
                index,
                block.start_offset,
                block.end_offset,
                block.text,
                hashlib.sha256(block.text.encode()).hexdigest(),
                "json_pointer",
                None,
                block.block_type.removeprefix("field:"),
            )
            for index, block in enumerate(parsed.blocks)
        ),
        "public",
        None,
        STAMP,
        attach_full_block_evidence=False,
    )
    session.execute(
        insert(event_documents).values(
            event_id=seeded["event_id"],
            revision_id=revision.revision_id,
            active=True,
            associated_at=STAMP,
        )
    )


def add_source_grades(engine, seeded, *, scores=(9.8,), freshness="current"):
    payload = nvd_payload()
    metrics = payload["cve"]["metrics"]["cvssMetricV31"]
    template = metrics[0]
    payload["cve"]["metrics"]["cvssMetricV31"] = [
        {**template, "cvssData": {**template["cvssData"], "baseScore": score}} for score in scores
    ]
    body = json.dumps(payload).encode()
    parsed = parse_json_document(body)
    source_id, document_id = str(uuid4()), str(uuid4())
    scope = seeded["rule"].scope
    with Session(engine) as session, session.begin():
        prepare_fixture_source_inputs(session, seeded)
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,visibility,tenant_id,"
                "created_at) "
                "VALUES (:id,:name,'structured_vulnerability',"
                "'https://nvd.nist.gov',:visibility,:tenant,:stamp)"
            ),
            {
                "id": source_id,
                "name": "Synthetic CVSS source " + source_id,
                "visibility": scope.visibility,
                "tenant": scope.tenant_id,
                "stamp": STAMP,
            },
        )
        content = register_response_content(session, seeded["store"], body, STAMP)
        session.execute(
            insert(documents).values(
                document_id=document_id,
                source_id=source_id,
                kind="advisory",
                title="Synthetic NVD grade",
                retrieved_at=STAMP,
                content_hash=content.content_hash,
                visibility=scope.visibility,
                tenant_id=scope.tenant_id,
                schema_version=2,
            )
        )
        revision = save_document_revision(
            session, seeded["store"], document_id, body, scope.visibility, scope.tenant_id, STAMP
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == revision.revision_id)
            .values(
                parse_status="parsed",
                canonical_uri="https://nvd.nist.gov/vuln/detail/" + CVE,
                source_metadata={"data_mode": "fixture", "content_coverage": "full_text"},
                first_observed_at=STAMP,
            )
        )
        register_source_revision_blocks(
            session,
            revision.revision_id,
            tuple(
                SourceRevisionBlock(
                    index,
                    block.start_offset,
                    block.end_offset,
                    block.text,
                    hashlib.sha256(block.text.encode()).hexdigest(),
                    "json_pointer",
                    None,
                    block.block_type.removeprefix("field:"),
                )
                for index, block in enumerate(parsed.blocks)
            ),
            scope.visibility,
            scope.tenant_id,
            STAMP,
            attach_full_block_evidence=False,
        )
        session.execute(
            insert(event_documents).values(
                event_id=seeded["event_id"],
                revision_id=revision.revision_id,
                active=True,
                associated_at=STAMP,
            )
        )
        session.execute(
            insert(event_external_ids).values(
                event_id=seeded["event_id"],
                id_type="cve",
                id_value=CVE,
                scope_key="public" if scope.visibility == "public" else "tenant:" + scope.tenant_id,
            )
        )
        loaded = load_event_enrichment_inputs(
            session,
            seeded["store"],
            seeded["author"],
            UUID(seeded["event_id"]),
            "risk-pg-fixture-1",
        )
        attempt = next(
            item
            for item in enrich_structured_fields(loaded.context, loaded.documents)
            if item.dimension == "cvss"
        )
        grades = []
        for candidate in attempt.candidates:
            claim_id = str(uuid4())
            links = []
            for span in candidate.evidence:
                document = next(
                    item for item in loaded.documents if item.revision_id == span.revision_id
                )
                block = next(item for item in document.blocks if item.block_id == span.block_id)
                identifier = attach_evidence_span(
                    session,
                    str(span.revision_id),
                    block.start_offset + span.start_offset,
                    block.start_offset + span.end_offset,
                    block.json_pointer,
                    span.quote_text,
                    True,
                    scope.visibility,
                    scope.tenant_id,
                    STAMP,
                    str(span.block_id),
                    span.quote_sha256,
                    STAMP,
                )
                links.append(
                    EvidenceLink(
                        evidence_id=Identifier(value=identifier),
                        support_kind="supports",
                        validation_status="validated",
                    )
                )
            primary = next(
                block
                for document in loaded.documents
                for block in document.blocks
                if block.block_id == candidate.evidence[0].block_id
            )
            record = ClaimRecord(
                schema_version=3,
                claim_id=Identifier(value=claim_id),
                subject="event:" + seeded["event_id"],
                predicate="cvss_signal",
                object_value=candidate.value,
                claim_status="supported",
                claim_origin="structured_source",
                condition_value="unknown",
                freshness=freshness,
                asserted_at=STAMP,
                observed_at=next(
                    item.observed_at
                    for item in loaded.documents
                    if item.revision_id == candidate.evidence[0].revision_id
                ),
                scope=scope,
            )
            KnowledgeRepository(session, seeded["author"]).publish(
                "risk-fixture-grade-" + claim_id,
                scope,
                (
                    ClaimSubmission(
                        record=record,
                        source_id=Identifier(value=source_id),
                        revision_id=Identifier(value=revision.revision_id),
                        json_path=primary.json_pointer,
                        scoring_authority=candidate.value.authority,
                        evidence_links=tuple(links),
                    ),
                ),
                created_at=STAMP,
            )
            grades.append(claim_id)
    return {
        "source_id": source_id,
        "document_id": document_id,
        "revision_id": revision.revision_id,
        "claim_ids": tuple(grades),
        "body": body,
    }


def create_current_case(engine, directory, *, scores=(9.8,), freshness="current"):
    seeded = original.seed(engine, directory)
    grade = add_source_grades(engine, seeded, scores=scores, freshness=freshness)
    original.publish(engine, seeded)
    asset = original.asset(engine, seeded)
    service = original.assessor(engine, seeded)
    receipt = service.commit(
        service.prepare(asset.asset_id, asset.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    return seeded, grade, asset, service, receipt


def read_risk(engine, seeded, service, *, version="1.4.1"):
    with Session(engine) as session, session.begin():
        scope = lock_authenticated_scope(
            session.connection(), seeded["asset_token"], datetime.now(UTC)
        )
        envelope = build_current_stack_envelope(
            fixture_request(version=version),
            service,
            KnowledgeReadService(session, scope, "fixture"),
        )
        assert (
            lock_authenticated_scope(session.connection(), seeded["asset_token"], datetime.now(UTC))
            == scope
        )
        return envelope


def test_actual_pg_same_event_current_rule_assessment_and_full_grade_citations(pg_engine, tmp_path):
    seeded, grade, _asset, service, receipt = create_current_case(pg_engine, tmp_path)
    result = read_risk(pg_engine, seeded, service)
    assert (
        result.risk_summary.confirmation == "confirmed"
        and result.risk_summary.coverage == "complete"
    )
    finding = result.risk_summary.findings[0]
    assert str(finding.assessment_id) == receipt.assessment_id
    assert (
        str(finding.event_id) == seeded["event_id"]
        and str(finding.grading_claim_id) in grade["claim_ids"]
    )
    assert finding.cvss_score == 9.8 and finding.cvss_version == "3.1"
    assert len(finding.citations) == 5 and CVE in {item.quote for item in finding.citations}


def test_actual_pg_current_below_threshold_grade_is_a_bounded_negative(pg_engine, tmp_path):
    seeded, _grade, _asset, service, _receipt = create_current_case(
        pg_engine, tmp_path, scores=(6.9,)
    )
    result = read_risk(pg_engine, seeded, service)
    assert (
        result.risk_summary.confirmation == "none_confirmed"
        and result.risk_summary.coverage == "complete"
    )
    assert result.risk_summary.findings[0].cvss_score == 6.9


def test_actual_pg_unknown_grade_freshness_is_not_upgraded_by_source_report(pg_engine, tmp_path):
    seeded, _grade, _asset, service, _receipt = create_current_case(
        pg_engine, tmp_path, freshness="unknown"
    )
    result = read_risk(pg_engine, seeded, service)
    assert (
        result.risk_summary.confirmation == "unknown" and result.risk_summary.coverage != "complete"
    )
    assert not result.risk_summary.findings


def test_actual_pg_conflicting_sources_cannot_be_resolved_by_authority_label(pg_engine, tmp_path):
    seeded, _grade, _asset, service, _receipt = create_current_case(
        pg_engine, tmp_path, scores=(9.8, 1.0)
    )
    result = read_risk(pg_engine, seeded, service)
    assert result.risk_summary.confirmation == "conflict" and not result.risk_summary.findings


def test_actual_pg_source_revision_replaces_previous_grade_without_false_negative(
    pg_engine, tmp_path
):
    seeded, grade, _asset, service, _receipt = create_current_case(pg_engine, tmp_path)
    with Session(pg_engine) as session, session.begin():
        save_document_revision(
            session,
            seeded["store"],
            grade["document_id"],
            grade["body"] + b" ",
            "tenant",
            seeded["tenant"],
            STAMP + timedelta(seconds=1),
        )
    result = read_risk(pg_engine, seeded, service)
    assert result.risk_summary.confirmation == "unknown" and not result.risk_summary.findings


def test_actual_pg_asset_change_cannot_reuse_old_applicability_with_current_grade(
    pg_engine, tmp_path
):
    seeded, _grade, asset, service, receipt = create_current_case(pg_engine, tmp_path)
    original.asset(pg_engine, seeded, "2.0", asset_id=asset.asset_id)
    result = read_risk(pg_engine, seeded, service)
    assert result.risk_summary.confirmation == "unknown" and not result.risk_summary.findings
    assert service.read(receipt.assessment_id).freshness == "stale"


def test_actual_pg_foreign_tenant_cannot_borrow_identical_component_and_grade(pg_engine, tmp_path):
    create_current_case(pg_engine, tmp_path / "first")
    foreign = original.seed(pg_engine, tmp_path / "foreign")
    result = read_risk(pg_engine, foreign, original.assessor(pg_engine, foreign))
    assert result.risk_summary.confirmation == "unknown" and not result.risk_summary.findings
    assert not result.result.results[0].citations


def test_actual_pg_grade_source_acl_change_fails_closed(pg_engine, tmp_path):
    seeded, grade, _asset, service, _receipt = create_current_case(pg_engine, tmp_path)
    with pg_engine.begin() as connection:
        connection.execute(
            text("UPDATE sources SET tenant_id=:tenant WHERE source_id=:source"),
            {"tenant": "synthetic-foreign", "source": grade["source_id"]},
        )
    with pytest.raises(CrossTenantAccessError):
        read_risk(pg_engine, seeded, service)


def test_actual_pg_revoked_actor_cannot_read_even_unknown_request(pg_engine, tmp_path):
    seeded, _grade, _asset, service, _receipt = create_current_case(pg_engine, tmp_path)
    fixture_now = datetime.now(UTC)
    with pg_engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(
                auth_sessions.c.session_hash
                == hashlib.sha256(seeded["asset_token"].encode()).hexdigest()
            )
            .values(
                issued_at=fixture_now - timedelta(seconds=2),
                expires_at=fixture_now - timedelta(seconds=1),
            )
        )
    with pytest.raises(SessionExpiredError):
        read_risk(pg_engine, seeded, service, version=None)


def test_actual_pg_multiple_relevant_rules_remain_explicitly_unrepresentable(pg_engine, tmp_path):
    seeded, _grade, asset, service, _receipt = create_current_case(pg_engine, tmp_path)
    second = {**seeded, "rule": seeded["rule"].model_copy(update={"rule_id": str(uuid4())})}
    second["service"].create_candidate(second["rule"], (second["binding"],))
    original.publish(pg_engine, second)
    for rule in (seeded["rule"], second["rule"]):
        service.commit(service.prepare(asset.asset_id, asset.snapshot.snapshot_id, rule.rule_id, 1))
    result = read_risk(pg_engine, seeded, service)
    assert result.risk_summary.confirmation == "unknown" and not result.risk_summary.findings
    assert "multiple_rules_require_public_component_envelope_extension" in result.result.limitations


def test_actual_pg_producer_does_not_create_business_rows_or_commit_callers_transaction(
    pg_engine, tmp_path
):
    seeded, _grade, _asset, service, _receipt = create_current_case(pg_engine, tmp_path)
    with pg_engine.connect() as connection:
        before = connection.scalar(select(func.count()).select_from(assessment_results))
    with Session(pg_engine) as session, session.begin():
        scope = lock_authenticated_scope(
            session.connection(), seeded["asset_token"], datetime.now(UTC)
        )
        result = build_current_stack_envelope(
            fixture_request(version="1.4.1"),
            service,
            KnowledgeReadService(session, scope, "fixture"),
        )
        assert result.risk_summary.confirmation == "confirmed" and session.in_transaction()
        session.rollback()
    with pg_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(assessment_results)) == before
