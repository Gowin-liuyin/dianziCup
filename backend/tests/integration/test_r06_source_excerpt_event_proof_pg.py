"""Fixture publications use real PG, dimension state, graph and authenticated Reader gates."""

import hashlib
import json
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.authentication import Principal
from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion import source_documents
from ai_intel.ingestion.source_documents import SourceResponse, persist_source_response
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.tool_contracts import ReadEvidenceArguments, ReadEvidenceCall
from ai_intel.investigation.tool_gateway import BudgetLimits, PostgresEvidenceReader, ToolGateway
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService
from ai_intel.knowledge.models import document_revisions, evidence, text_blocks, users
from ai_intel.knowledge.persistence_models import claim_evidence, claims, event_external_ids
from ai_intel.knowledge.revisions import QuoteConsistencyError

pytestmark = pytest.mark.real_pg
ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_r06_source_excerpt_event_proof_20261016"
# pg_case 输出目录默认即 RUN（原始冻结证据目录）；重跑环境可用环境变量把"写"改指
# 专属目录，避免覆盖既有冻结证据；输入夹具读取始终走 RUN。
TRACE_DIR = Path(os.environ.get("R06_PROOF_TRACE_DIR", str(RUN)))
NOW = datetime(2026, 10, 16, 10, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("fixture-source-proof-admin", None, Role.SYSTEM_ADMIN)
NVD_URL = (
    "https://services.nvd.nist.gov/rest/json/cves/2.0"
    "?keywordSearch=ollama&resultsPerPage=1&startIndex=0"
)
VENDOR_URL = (
    "https://api.github.com/repos/vllm-project/vllm/security-advisories"
    "?per_page=1&state=published&page=1"
)


@pytest.fixture
def proof_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r06_source_event_proof_20261016"
    assert os.environ["DIANZI_TEST_RUN_ID"] == "r06_source_event_proof_20261016"
    schema = "test_r06_source_event_proof_" + uuid4().hex
    base = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000"}
    )
    engine = create_engine(scoped, poolclass=NullPool, hide_parameters=True)
    try:
        run_migrations(scoped.render_as_string(hide_password=False))
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def response(kind="nvd_ollama", *, payload=None):
    if kind == "nvd_ollama":
        body = (RUN / "nvd-response.json").read_bytes()
        url = NVD_URL
    else:
        body = (ROOT / "fixtures/recorded/vllm_vendor_20261015_public.json").read_bytes()
        url = VENDOR_URL
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode()
    return SourceResponse(kind, body, url, NOW, data_mode="fixture")


def publish(engine, store, source_response):
    with Session(engine) as session, session.begin():
        return persist_source_response(session, store, ADMIN, source_response, ingested_at=NOW)


def excerpt_arguments(engine, saved, *, index=0):
    with engine.connect() as connection:
        span = connection.scalar(
            select(evidence.c.evidence_id)
            .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
            .join(claims, claims.c.claim_id == claim_evidence.c.claim_id)
            .where(
                claims.c.predicate == "source_excerpt",
                evidence.c.revision_id == saved.revision_ids[index],
                evidence.c.locator.in_(("/cve/descriptions/0/value", "/description", "/summary")),
            )
        )
    assert span is not None
    return ReadEvidenceArguments(
        event_id=UUID(saved.event_ids[index]),
        evidence_id=UUID(span),
        revision_id=UUID(saved.revision_ids[index]),
    )


def read(engine, register, arguments):
    user_id, token = str(uuid4()), secrets.token_urlsafe(32)
    register(SecretStr(token))
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                user_id=user_id,
                username="fixture-proof-" + uuid4().hex,
                password_hash="fixture-unused",
                tenant_id="fixture-owner",
                role="analyst",
                created_at=now,
            )
        )
        connection.execute(
            auth_sessions.insert().values(
                session_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user_id,
                csrf_token="fixture-unused",
                issued_at=now,
                expires_at=now + timedelta(minutes=5),
            )
        )
    with engine.connect() as connection:
        gateway = ToolGateway(
            Principal(user_id, "fixture-owner", Role.ANALYST),
            uuid4(),
            BudgetLimits(
                max_calls=1,
                max_concurrent_calls=1,
                max_request_bytes=4096,
                max_total_input_bytes=4096,
                max_result_bytes=16384,
                max_total_output_bytes=16384,
                deadline_monotonic=time.monotonic() + 8,
            ),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        call = ReadEvidenceCall(tool_name="read_evidence", arguments=arguments, goal_id=uuid4())
        return gateway.execute(AgentRole.QA, call.model_dump_json().encode())


def graph(engine, event_id):
    scope = AccessScope.for_authenticated_user("fixture-proof-reader", None, Role.ANALYST)
    with Session(engine) as session, session.begin():
        return EvidenceGraphReadService(session, scope).event_graph(event_id)


def trace(engine, arguments, result, name):
    snapshot = graph(engine, arguments.event_id)
    with engine.connect() as connection:
        spans = [
            dict(row)
            for row in connection.execute(
                select(
                    evidence.c.evidence_id,
                    evidence.c.revision_id,
                    evidence.c.quote,
                    evidence.c.start_offset,
                    evidence.c.end_offset,
                    evidence.c.locator,
                    evidence.c.quote_sha256,
                    text_blocks.c.block_text,
                    text_blocks.c.start_offset.label("block_start"),
                    text_blocks.c.json_pointer,
                )
                .join(text_blocks, text_blocks.c.block_id == evidence.c.block_id)
                .where(evidence.c.revision_id == str(arguments.revision_id))
            ).mappings()
        ]
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    (TRACE_DIR / ("pg_case_" + name + ".json")).write_text(
        json.dumps(
            {
                "data_mode": "fixture",
                "model_calls": 0,
                "http_requests": 0,
                "reader": result.model_dump(mode="json"),
                "graph": snapshot.model_dump(mode="json"),
                "spans": spans,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "kind,cve_id", [("nvd_ollama", None), ("vllm_vendor", None), ("vllm_vendor", "CVE-2026-12345")]
)
def test_production_text_publication_reader_support_and_replay(
    proof_engine,
    tmp_path,
    register_sensitive_failure_value,
    kind,
    cve_id,
):
    source_response = response(kind)
    if cve_id is not None:
        payload = json.loads(source_response.body)
        payload[0]["cve_id"] = cve_id
        source_response = response(kind, payload=payload)
    store = ContentStore(tmp_path)
    saved = publish(proof_engine, store, source_response)
    arguments = excerpt_arguments(proof_engine, saved)
    result = read(proof_engine, register_sensitive_failure_value, arguments)
    assert result.status.value == "succeeded"
    assert result.data is not None and result.data.data_mode == "fixture"
    assert result.is_synthetic is True
    snapshot = graph(proof_engine, arguments.event_id)
    same_event = [edge for edge in snapshot.edges if edge.relation_type == "same_event"]
    assert any(arguments.evidence_id in edge.evidence_span_ids for edge in same_event)
    assert any(len(edge.evidence_span_ids) >= 2 for edge in same_event)
    with proof_engine.connect() as connection:
        for row in connection.execute(
            select(
                evidence, text_blocks.c.block_text, text_blocks.c.start_offset.label("block_start")
            ).join(text_blocks, text_blocks.c.block_id == evidence.c.block_id)
        ).mappings():
            start, end = (
                row["start_offset"] - row["block_start"],
                row["end_offset"] - row["block_start"],
            )
            assert row["block_text"][start:end] == row["quote"]
            assert hashlib.sha256(row["quote"].encode()).hexdigest() == row["quote_sha256"]
        count = connection.scalar(select(func.count()).select_from(evidence))
        if kind == "nvd_ollama":
            dimension = connection.execute(select(enrichment_results)).mappings().one()
            assert dimension["dimension"] == "cvss" and dimension["status"] == "available"
            assert (
                store.read_verified(saved.response_content_hash)
                == (RUN / "nvd-response.json").read_bytes()
            )
    replayed = publish(proof_engine, store, source_response)
    assert replayed.new_revision_count == 0 and replayed.revision_ids == saved.revision_ids
    with proof_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(evidence)) == count
    trace(proof_engine, arguments, result, kind + ("_cve" if cve_id else ""))


@pytest.mark.parametrize(
    "mutation", ["wrong_event", "retired", "legacy_no_owner", "reference_only"]
)
def test_missing_or_invalid_event_binding_stays_partial(
    proof_engine,
    tmp_path,
    register_sensitive_failure_value,
    mutation,
):
    source_response = response()
    if mutation == "reference_only":
        payload = json.loads(source_response.body)
        payload["vulnerabilities"][0]["cve"]["references"].append(
            {"url": "https://example.invalid/CVE-2024-34359"}
        )
        source_response = response(payload=payload)
    saved = publish(proof_engine, ContentStore(tmp_path), source_response)
    arguments = excerpt_arguments(proof_engine, saved)
    with proof_engine.begin() as connection:
        if mutation == "wrong_event":
            connection.execute(update(event_external_ids).values(id_value="CVE-2024-99999"))
        elif mutation == "retired":
            connection.execute(update(document_revisions).values(is_current=False))
        else:
            owners = select(evidence.c.evidence_id).where(evidence.c.locator == "/cve/id")
            connection.execute(
                delete(claim_evidence).where(claim_evidence.c.evidence_id.in_(owners))
            )
    result = read(proof_engine, register_sensitive_failure_value, arguments)
    assert result.status.value == "partial"
    assert result.error_code == "evidence_not_current_supported"
    assert not graph(proof_engine, arguments.event_id).edges
    trace(proof_engine, arguments, result, mutation)


def test_revision_replacement_retains_history_and_revalidates_new_proofs(
    proof_engine,
    tmp_path,
    register_sensitive_failure_value,
):
    store = ContentStore(tmp_path)
    first = publish(proof_engine, store, response())
    old = excerpt_arguments(proof_engine, first)
    payload = json.loads(response().body)
    payload["vulnerabilities"][0]["cve"]["descriptions"][0]["value"] += " Source correction."
    second = publish(proof_engine, store, response(payload=payload))
    assert second.event_ids == first.event_ids and second.revision_ids != first.revision_ids
    assert read(proof_engine, register_sensitive_failure_value, old).status.value == "partial"
    current = excerpt_arguments(proof_engine, second)
    assert read(proof_engine, register_sensitive_failure_value, current).status.value == "succeeded"
    with proof_engine.connect() as connection:
        assert connection.scalar(
            select(evidence.c.quote).where(evidence.c.evidence_id == str(old.evidence_id))
        )


@pytest.mark.parametrize("foreign", ["another_member", "older_revision"])
def test_owner_block_from_another_member_or_revision_is_rejected_and_rolled_back(
    proof_engine,
    tmp_path,
    monkeypatch,
    foreign,
):
    store = ContentStore(tmp_path)
    prior = publish(proof_engine, store, response())
    with proof_engine.connect() as connection:
        owner = connection.scalar(
            select(text_blocks.c.block_id).where(text_blocks.c.json_pointer == "/cve/id")
        )
        counts = tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (claims, evidence, document_revisions)
        )
    payload = json.loads(response().body)
    cve = payload["vulnerabilities"][0]["cve"]
    if foreign == "another_member":
        cve["id"] = "CVE-2024-99999"
    cve["descriptions"][0]["value"] += " Corrected member text."
    attach = source_documents.attach_evidence_span

    def substitute_owner(*args, **kwargs):
        if args[4] == "/cve/id":
            kwargs["block_id"] = owner
        return attach(*args, **kwargs)

    monkeypatch.setattr(source_documents, "attach_evidence_span", substitute_owner)
    with pytest.raises(QuoteConsistencyError, match="different revision"):
        publish(proof_engine, store, response(payload=payload))
    with proof_engine.connect() as connection:
        assert (
            tuple(
                connection.scalar(select(func.count()).select_from(table))
                for table in (claims, evidence, document_revisions)
            )
            == counts
        )
        assert (
            connection.scalar(
                select(document_revisions.c.is_current).where(
                    document_revisions.c.revision_id == prior.revision_ids[0]
                )
            )
            is True
        )


def test_reader_argument_for_wrong_revision_fails(
    proof_engine,
    tmp_path,
    register_sensitive_failure_value,
):
    saved = publish(proof_engine, ContentStore(tmp_path), response())
    arguments = excerpt_arguments(proof_engine, saved).model_copy(update={"revision_id": uuid4()})
    result = read(proof_engine, register_sensitive_failure_value, arguments)
    assert result.status.value == "failed"


def test_missing_cve_cannot_be_recovered_from_ssvc_or_reference_url(proof_engine, tmp_path):
    payload = json.loads(response().body)
    del payload["vulnerabilities"][0]["cve"]["id"]
    with pytest.raises(source_documents.SourceDocumentError):
        publish(proof_engine, ContentStore(tmp_path), response(payload=payload))
    with proof_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(claims)) == 0
