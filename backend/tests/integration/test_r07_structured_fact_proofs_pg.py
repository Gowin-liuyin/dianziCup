"""Isolated PG facts and synthetic source bytes exercise the real bounded bridge.

Each case keeps its own schema for audit. No schema/database teardown, source HTTP,
model, shared business database or fake proof result is used.
"""

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema
from test_r07_public_signals import cwe_document
from tests.r06_source_worker_fixtures import source_response

from ai_intel.api.actor_references import (
    ActorReference,
    create_actor_reference,
    lock_actor_reference_scope,
)
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.credentials import SessionCredential
from ai_intel.api.document_read_service import sources
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.enums import DimensionStatus
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.contracts import DimensionAttempt, EvidenceBoundCandidate
from ai_intel.enrichment.inputs import load_event_enrichment_inputs
from ai_intel.enrichment.publication import publish_enrichment_attempts
from ai_intel.enrichment.signal_sources import select_public_signal_document
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_documents import (
    SourceResponse,
    persist_source_response,
    source_data_mode_metadata,
)
from ai_intel.knowledge.event_linking import EventRepository, EventSubmission
from ai_intel.knowledge.models import document_revisions, documents, evidence, text_blocks, users
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.knowledge.revisions import (
    SourceRevisionBlock,
    register_response_content,
    register_source_revision_blocks,
    save_document_revision,
)
from ai_intel.knowledge.structured_fact_proofs import (
    StructuredFactProofChangedError,
    StructuredFactProofReader,
    StructuredFactProofRequest,
)

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, tzinfo=UTC)
DATABASE = "test_dianzi_r07_structured_fact_proof_fix1_20261016"


@pytest.fixture()
def proof_engine(isolated_test_database_url, register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    url = make_url(isolated_test_database_url)
    assert url.database == DATABASE and url.host == "127.0.0.1" and url.port == 25432
    if url.password:
        register_sensitive_failure_value(SecretStr(url.password))
    schema = "r07_fact_proof_fix1_" + uuid4().hex
    root_engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with root_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=5000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, poolclass=NullPool, hide_parameters=True)
    try:
        yield engine
    finally:
        engine.dispose()
        root_engine.dispose()


def seed_actor(engine, register, tenant=None, role=Role.SYSTEM_ADMIN):
    user_id, token = str(uuid4()), secrets.token_urlsafe(32)
    register(SecretStr(token))
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                user_id=user_id,
                username="fact-proof-" + uuid4().hex,
                password_hash="fixture-unused",
                tenant_id=tenant,
                role=role.value,
                created_at=now,
            )
        )
        connection.execute(
            auth_sessions.insert().values(
                session_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user_id,
                csrf_token="fixture-unused",
                issued_at=now,
                expires_at=now + timedelta(minutes=10),
            )
        )
        actor = create_actor_reference(connection, SessionCredential(SecretStr(token)), now)
        scope = lock_actor_reference_scope(connection, actor, now)
    return actor, scope


def add_document(engine, store, source, event_id, scope):
    source_id, document_id = str(uuid4()), str(uuid4())
    parsed = parse_json_document(source.json_payload)
    with Session(engine) as session, session.begin():
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES(:id,:name,:category,:origin,'public',NULL,:at)"
            ),
            {
                "id": source_id,
                "name": "Synthetic recorded signal fixture",
                "category": source.source_category.value,
                "origin": str(source.canonical_uri),
                "at": NOW,
            },
        )
        stored = register_response_content(session, store, source.json_payload, NOW)
        session.execute(
            documents.insert().values(
                document_id=document_id,
                source_id=source_id,
                kind=source.document_kind.value,
                title="Synthetic source signal",
                retrieved_at=NOW,
                content_hash=stored.content_hash,
                visibility="public",
                tenant_id=None,
                schema_version=2,
            )
        )
        saved = save_document_revision(
            session,
            store,
            document_id,
            source.json_payload,
            "public",
            None,
            NOW,
            revision_metadata={
                **source_data_mode_metadata("fixture"),
                "content_coverage": "full_text",
                "version_label": source.source_version or "fixture-signal-1",
            },
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == saved.revision_id)
            .values(
                canonical_uri=str(source.canonical_uri),
                parse_status="parsed",
                first_observed_at=NOW,
                ingested_at=NOW,
                normalizer_version="fixture-signal-1",
            )
        )
        register_source_revision_blocks(
            session,
            saved.revision_id,
            tuple(
                SourceRevisionBlock(
                    index,
                    block.start_offset,
                    block.end_offset,
                    block.text,
                    hashlib.sha256(block.text.encode()).hexdigest(),
                    block.block_type,
                    None,
                    block.block_type.removeprefix("field:"),
                )
                for index, block in enumerate(parsed.blocks)
            ),
            "public",
            None,
            NOW,
            attach_full_block_evidence=True,
        )
        old = EventRepository(session, scope).get_source_revisions(str(event_id))
        EventRepository(session, scope).publish_events(
            "fixture-add-signal-" + source_id,
            VisibilityScope(visibility="public"),
            (
                EventSubmission(
                    event_id=Identifier(value=str(event_id)),
                    event_type="vulnerability",
                    title="Synthetic CVE",
                    scope=VisibilityScope(visibility="public"),
                    source_revision_ids=tuple(
                        Identifier(value=revision) for revision in (*old, saved.revision_id)
                    ),
                ),
            ),
            created_at=NOW,
        )


@dataclass
class FixtureFacts:
    actor: ActorReference
    scope: AccessScope
    store: ContentStore
    request: StructuredFactProofRequest
    claim_id: str


def seed_facts(engine, tmp_path, register, dimension="cvss", conflict=False, two_members=False):
    actor, scope = seed_actor(engine, register)
    body, _media = source_response("nvd_ollama")
    payload = json.loads(body)
    cve = payload["vulnerabilities"][0]["cve"]
    cve_id = cve["id"]
    if two_members:
        other = json.loads(json.dumps(payload["vulnerabilities"][0]))
        other["cve"]["id"] = "CVE-2024-99999"
        payload["vulnerabilities"].append(other)
        payload["totalResults"] = 2
        payload["resultsPerPage"] = 2
    if dimension == "cwe":
        cve["weaknesses"] = [{"description": [{"lang": "en", "value": "CWE-78"}]}]
    if conflict:
        metrics = cve["metrics"]["cvssMetricV31"]
        extra = json.loads(json.dumps(metrics[0]))
        extra["cvssData"]["baseScore"] = 1.0
        metrics.append(extra)
    store = ContentStore(tmp_path / "content")
    with Session(engine) as session, session.begin():
        source = persist_source_response(
            session,
            store,
            scope,
            SourceResponse(
                "nvd_ollama",
                json.dumps(payload).encode(),
                "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=100&startIndex=0",
                NOW,
                data_mode="fixture",
            ),
            ingested_at=NOW,
        )
    event_id = UUID(source.event_ids[0])
    if dimension == "epss":
        from test_r07_public_signals import document

        raw = json.dumps(
            {
                "status": "OK",
                "status-code": 200,
                "version": "1.0",
                "total": 1,
                "offset": 0,
                "limit": 100,
                "data": [{"cve": cve_id, "epss": "0.0", "percentile": "0.1", "date": "2026-10-14"}],
            }
        ).encode()
        selected = select_public_signal_document("epss", raw, cve_id)
        auxiliary = document(json.loads(selected.payload), selected.canonical_uri)
        add_document(engine, store, auxiliary, event_id, scope)
    elif dimension == "kev":
        from test_r07_public_signals import document

        raw = json.dumps(
            {
                "catalogVersion": "2026.10.16",
                "dateReleased": "2026-10-16T00:00:00Z",
                "count": 1,
                "vulnerabilities": [
                    {
                        "cveID": cve_id,
                        "dateAdded": "2026-09-01",
                        "requiredAction": "Apply updates.",
                        "dueDate": "2026-09-22",
                        "knownRansomwareCampaignUse": "Known",
                    }
                ],
            }
        ).encode()
        selected = select_public_signal_document("kev", raw, cve_id)
        add_document(
            engine,
            store,
            document(json.loads(selected.payload), selected.canonical_uri),
            event_id,
            scope,
        )
    elif dimension == "cwe":
        add_document(engine, store, cwe_document(version="4.19"), event_id, scope)
    with Session(engine) as session, session.begin():
        loaded = load_event_enrichment_inputs(session, store, scope, event_id, "fixture-proof-1")
        cvss = next(
            attempt
            for attempt in enrich_structured_fields(loaded.context, loaded.documents)
            if attempt.dimension == "cvss"
        )
        if dimension == "versions":
            candidate = EvidenceBoundCandidate(
                dimension="versions",
                value={
                    "kind": "version_assertion",
                    "package_key": "fixture-package",
                    "ecosystem": "unknown",
                    "scheme": "unknown",
                    "raw_expression": "Unconfirmed synthetic range",
                },
                evidence=cvss.candidates[0].evidence,
                origin="model_hypothesis",
            )
            attempt = DimensionAttempt(
                dimension="versions", status=DimensionStatus.PENDING, candidates=(candidate,)
            )
        else:
            attempt = next(
                item
                for item in enrich_structured_fields(loaded.context, loaded.documents)
                if item.dimension == dimension
            )
        published = publish_enrichment_attempts(
            session, scope, loaded, (attempt,), request_id=uuid4(), recorded_at=NOW
        )
        claim_id = published[0].claim_ids[0]
        rows = (
            session.execute(
                select(evidence)
                .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
                .where(claim_evidence.c.claim_id == claim_id)
            )
            .mappings()
            .all()
        )
        span = next(
            row
            for row in rows
            if row["revision_id"] == str(attempt.candidates[0].evidence[0].revision_id)
        )
        request = StructuredFactProofRequest(
            event_id=event_id,
            evidence_id=UUID(span["evidence_id"]),
            revision_id=UUID(span["revision_id"]),
        )
    return FixtureFacts(actor, scope, store, request, claim_id)


def read_facts(engine, facts, store=None, scope=None, actor=None, seconds=5):
    with engine.connect() as connection:
        reader = StructuredFactProofReader(
            connection, actor or facts.actor, scope or facts.scope, store or facts.store, "fixture"
        )
        result = reader.read(facts.request, time.monotonic() + seconds)
        assert not connection.in_transaction()
        return result


@pytest.mark.parametrize("dimension", ("cvss", "epss", "kev"))
def test_actual_source_loader_publisher_and_bridge_return_saved_report(
    proof_engine, tmp_path, register_sensitive_failure_value, dimension
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value, dimension)
    result = read_facts(proof_engine, facts)
    assert result.status == "reported" and len(result.facts) == 1
    report = result.facts[0]
    assert report.report_support == "verified" and report.record.condition_value.value == "unknown"
    assert report.record.freshness.value == "unknown" and report.record.subject.startswith("event:")
    assert facts.request.evidence_id in {item.span_id for item in report.supporting_evidence}
    assert result.data_mode == "fixture"


@pytest.mark.parametrize("condition", ("true", "false", "unknown", "conflict"))
def test_original_condition_is_never_promoted_or_negated(
    proof_engine, tmp_path, register_sensitive_failure_value, condition
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == facts.claim_id)
            .values(condition_value=condition)
        )
    result = read_facts(proof_engine, facts)
    assert result.facts[0].record.condition_value.value == condition
    assert result.status == ("partial" if condition == "conflict" else "reported")


@pytest.mark.parametrize(
    "changes,gap",
    (
        ({"claim_status": "disputed"}, "claim_disputed"),
        ({"freshness": "stale"}, "fact_stale"),
        ({"is_current": False}, "historical_fact_or_revision"),
    ),
)
def test_dispute_stale_or_history_keeps_original_record_without_verified_report(
    proof_engine, tmp_path, register_sensitive_failure_value, changes, gap
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.begin() as connection:
        connection.execute(
            update(claims).where(claims.c.claim_id == facts.claim_id).values(**changes)
        )
    result = read_facts(proof_engine, facts)
    assert result.status == "partial" and gap in result.missing_requirements
    assert (
        result.facts[0].report_support == "unverified" and not result.facts[0].supporting_evidence
    )


def test_old_revision_is_partial_without_relabeling_current(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.begin() as connection:
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == str(facts.request.revision_id))
            .values(is_current=False)
        )
    result = read_facts(proof_engine, facts)
    assert result.status == "partial" and not result.facts[0].revision_is_current


@pytest.mark.parametrize(
    "dimension,gap", (("cwe", "cwe_owner_evidence_missing"), ("versions", "unsupported_typed_fact"))
)
def test_incomplete_cwe_and_model_version_remain_explicit_partial(
    proof_engine, tmp_path, register_sensitive_failure_value, dimension, gap
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value, dimension)
    result = read_facts(proof_engine, facts)
    assert result.status == "partial" and gap in result.missing_requirements
    assert result.facts[0].report_support == "unverified"


def test_dimension_conflict_does_not_choose_one_source_score(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value, conflict=True)
    result = read_facts(proof_engine, facts)
    assert result.status == "partial" and "dimension_conflict" in result.missing_requirements
    assert result.conflicts and result.facts[0].record.claim_status.value == "supported"


def test_missing_raw_object_is_partial_not_a_false_empty_search(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)

    class MissingStore(ContentStore):
        def read_verified(self, digest):
            raise FileNotFoundError("fixture object unavailable")

    result = read_facts(proof_engine, facts, store=MissingStore(tmp_path / "missing"))
    assert result.status == "partial" and "source_object_missing" in result.missing_requirements


@pytest.mark.parametrize("parent", ("source", "document", "revision"))
def test_each_parent_revocation_denies_before_object_read(
    proof_engine, tmp_path, register_sensitive_failure_value, parent
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.begin() as connection:
        source_id, document_id = connection.execute(
            select(documents.c.source_id, documents.c.document_id)
            .join(document_revisions)
            .where(document_revisions.c.revision_id == str(facts.request.revision_id))
        ).one()
        relation, key, identifier = {
            "source": (sources, sources.c.source_id, source_id),
            "document": (documents, documents.c.document_id, document_id),
            "revision": (
                document_revisions,
                document_revisions.c.revision_id,
                str(facts.request.revision_id),
            ),
        }[parent]
        connection.execute(
            update(relation).where(key == identifier).values(visibility="tenant", tenant_id="other")
        )

    class NoReadStore(ContentStore):
        def read_verified(self, digest):
            pytest.fail("revoked input caused object IO")

    with pytest.raises(CrossTenantAccessError, match="resource_unavailable"):
        read_facts(proof_engine, facts, store=NoReadStore(tmp_path / "no-io"))


def test_actor_revocation_is_uniform_and_never_returns_fact_ids(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.user_id == facts.scope.user_id)
            .values(revoked_at=datetime.now(UTC))
        )
    with pytest.raises(CrossTenantAccessError, match="resource_unavailable"):
        read_facts(proof_engine, facts)


@pytest.mark.parametrize("mutation", ("owner_context", "wrong_score", "changed_block"))
def test_exact_quote_is_insufficient_for_owner_member_or_value(
    proof_engine, tmp_path, register_sensitive_failure_value, mutation
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.begin() as connection:
        if mutation == "owner_context":
            owner_id = connection.scalar(
                select(evidence.c.evidence_id)
                .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
                .join(text_blocks, text_blocks.c.block_id == evidence.c.block_id)
                .where(
                    claim_evidence.c.claim_id == facts.claim_id,
                    text_blocks.c.json_pointer == "/cve/id",
                )
            )
            connection.execute(
                update(claim_evidence)
                .where(
                    claim_evidence.c.claim_id == facts.claim_id,
                    claim_evidence.c.evidence_id == owner_id,
                )
                .values(support_kind="context")
            )
        elif mutation == "wrong_score":
            value = connection.scalar(
                select(claims.c.object_json).where(claims.c.claim_id == facts.claim_id)
            )
            value["base_score"] = 1.0
            connection.execute(
                update(claims).where(claims.c.claim_id == facts.claim_id).values(object_json=value)
            )
        else:
            block = (
                connection.execute(
                    select(text_blocks).where(
                        text_blocks.c.revision_id == str(facts.request.revision_id),
                        text_blocks.c.json_pointer == "/cve/id",
                    )
                )
                .mappings()
                .one()
            )
            altered = block["block_text"].replace("CVE-", "XXX-")
            connection.execute(
                update(text_blocks)
                .where(text_blocks.c.block_id == block["block_id"])
                .values(
                    block_text=altered, text_sha256=hashlib.sha256(altered.encode()).hexdigest()
                )
            )
    result = read_facts(proof_engine, facts)
    assert result.status == "partial" and result.facts[0].report_support == "unverified"


def test_io_has_no_actor_or_source_row_locks_and_revocation_is_rechecked(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)

    class RevokingStore(ContentStore):
        def read_verified(self, digest):
            payload = facts.store.read_verified(digest)
            with proof_engine.begin() as connection:
                connection.execute(
                    update(auth_sessions)
                    .where(auth_sessions.c.user_id == facts.scope.user_id)
                    .values(revoked_at=datetime.now(UTC))
                )
                connection.execute(update(sources).values(visibility="tenant", tenant_id="other"))
            return payload

    with pytest.raises(CrossTenantAccessError, match="resource_unavailable"):
        read_facts(proof_engine, facts, store=RevokingStore(tmp_path / "callback"))


def test_source_text_change_during_io_invalidates_snapshot(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)

    class ChangingStore(ContentStore):
        def read_verified(self, digest):
            payload = facts.store.read_verified(digest)
            with proof_engine.begin() as connection:
                connection.execute(
                    update(claims)
                    .where(claims.c.claim_id == facts.claim_id)
                    .values(freshness="stale")
                )
            return payload

    with pytest.raises(StructuredFactProofChangedError, match="fact_proof_inputs_changed"):
        read_facts(proof_engine, facts, store=ChangingStore(tmp_path / "callback"))


def test_deadline_is_not_extended_for_source_io(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)

    class SlowStore(ContentStore):
        calls = 0

        def read_verified(self, digest):
            self.calls += 1
            time.sleep(0.4)
            return facts.store.read_verified(digest)

    store = SlowStore(tmp_path / "slow")
    with pytest.raises(TimeoutError, match="fact_proof_deadline_exhausted"):
        read_facts(proof_engine, facts, store=store, seconds=0.3)
    assert store.calls == 1


def test_same_page_equal_score_other_member_does_not_own_requested_fact(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value, two_members=True)
    with proof_engine.connect() as connection:
        other_event = connection.scalar(
            select(events.c.event_id).where(events.c.event_id != str(facts.request.event_id))
        )
    facts.request = facts.request.model_copy(update={"event_id": UUID(other_event)})
    result = read_facts(proof_engine, facts)
    assert result.status == "not_found" and not result.facts


def test_owner_proof_from_legacy_sibling_claim_is_not_borrowed(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.begin() as connection:
        owner = connection.scalar(
            select(evidence.c.evidence_id)
            .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
            .join(text_blocks, text_blocks.c.block_id == evidence.c.block_id)
            .where(
                claim_evidence.c.claim_id == facts.claim_id, text_blocks.c.json_pointer == "/cve/id"
            )
        )
        connection.execute(
            update(claim_evidence)
            .where(
                claim_evidence.c.claim_id == facts.claim_id, claim_evidence.c.evidence_id == owner
            )
            .values(validation_status="unverified")
        )
        sibling_owner = connection.scalar(
            select(claim_evidence.c.evidence_id)
            .join(evidence, evidence.c.evidence_id == claim_evidence.c.evidence_id)
            .join(text_blocks, text_blocks.c.block_id == evidence.c.block_id)
            .where(
                claim_evidence.c.claim_id != facts.claim_id,
                text_blocks.c.json_pointer == "/cve/id",
                claim_evidence.c.validation_status == "validated",
            )
        )
        assert sibling_owner is not None
    result = read_facts(proof_engine, facts)
    assert result.status == "partial" and "owner_evidence_missing" in result.missing_requirements


def test_visible_legacy_evidence_without_typed_fact_is_not_found(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    with proof_engine.connect() as connection:
        span_id = connection.scalar(
            select(evidence.c.evidence_id)
            .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
            .join(claims, claims.c.claim_id == claim_evidence.c.claim_id)
            .where(
                evidence.c.revision_id == str(facts.request.revision_id),
                claims.c.schema_version < 3,
            )
            .limit(1)
        )
    assert span_id is not None
    facts.request = facts.request.model_copy(update={"evidence_id": UUID(span_id)})
    result = read_facts(proof_engine, facts)
    assert result.status == "not_found" and not result.facts


def test_same_tenant_report_and_cross_tenant_uniform_denial(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    owner_actor, owner_scope = seed_actor(
        proof_engine, register_sensitive_failure_value, tenant="tenant-a", role=Role.TENANT_ADMIN
    )
    other_actor, other_scope = seed_actor(
        proof_engine, register_sensitive_failure_value, tenant="tenant-b", role=Role.TENANT_ADMIN
    )
    with proof_engine.begin() as connection:
        for relation in (sources, documents, document_revisions, claims, evidence, events):
            connection.execute(update(relation).values(visibility="tenant", tenant_id="tenant-a"))
        connection.execute(update(events).values(scope_key="tenant:tenant-a"))
        connection.execute(update(event_external_ids).values(scope_key="tenant:tenant-a"))
    result = read_facts(proof_engine, facts, actor=owner_actor, scope=owner_scope)
    assert result.status == "reported" and result.facts[0].record.scope.tenant_id == "tenant-a"
    with pytest.raises(CrossTenantAccessError, match="resource_unavailable"):
        read_facts(proof_engine, facts, actor=other_actor, scope=other_scope)


def test_server_actor_and_access_scope_must_match(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    _other_actor, other_scope = seed_actor(proof_engine, register_sensitive_failure_value)
    with pytest.raises(CrossTenantAccessError, match="resource_unavailable"):
        read_facts(proof_engine, facts, scope=other_scope)


@pytest.mark.parametrize("during_io", (False, True))
def test_withdrawn_event_revision_never_signs_a_source_report(
    proof_engine, tmp_path, register_sensitive_failure_value, during_io
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)

    def withdraw():
        with proof_engine.begin() as connection:
            connection.execute(
                update(event_documents)
                .where(
                    event_documents.c.event_id == str(facts.request.event_id),
                    event_documents.c.revision_id == str(facts.request.revision_id),
                )
                .values(active=False, superseded_at=datetime.now(UTC))
            )

    class WithdrawingStore(ContentStore):
        calls = 0

        def read_verified(self, digest):
            self.calls += 1
            if not during_io:
                pytest.fail("withdrawn association caused source object IO")
            payload = facts.store.read_verified(digest)
            withdraw()
            return payload

    if not during_io:
        withdraw()
    store = WithdrawingStore(tmp_path / "withdraw-callback")
    result = read_facts(proof_engine, facts, store=store)
    assert result.status == "partial" and "event_document_withdrawn" in result.missing_requirements
    assert all(item.report_support == "unverified" for item in result.facts)
    assert result.facts[0].record.condition_value.value == "unknown"
    assert store.calls == int(during_io)


def test_primary_assertion_path_mismatch_keeps_original_path_and_partial(
    proof_engine, tmp_path, register_sensitive_failure_value
):
    facts = seed_facts(proof_engine, tmp_path, register_sensitive_failure_value)
    wrong_path = "/unrelated/other-owner/score"
    with proof_engine.begin() as connection:
        connection.execute(
            update(claim_assertions)
            .where(claim_assertions.c.claim_id == facts.claim_id)
            .values(json_path=wrong_path)
        )
    result = read_facts(proof_engine, facts)
    assert result.facts[0].primary_assertion_path == wrong_path
    assert (
        result.status == "partial"
        and "primary_assertion_path_mismatch" in result.missing_requirements
    )
    assert result.facts[0].report_support == "unverified"
