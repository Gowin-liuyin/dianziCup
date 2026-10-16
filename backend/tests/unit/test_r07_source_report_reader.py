"""Explicit offline fixtures exercise the shared reader through the enrichment factory."""

import time
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import Connection
from test_r07_public_signals import context, document, nvd_payload

from ai_intel.api.actor_references import _permissions_digest, actor_reference_from_payload
from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.enums import ClaimStatus
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment import inputs
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.enrichment.source_report_reader import build_source_report_reader
from ai_intel.infrastructure.content_store import ContentStorage, ContentStore
from ai_intel.knowledge import structured_fact_proofs as bridge

NOW = datetime(2026, 10, 17, tzinfo=UTC)


@pytest.fixture
def read_case(monkeypatch, tmp_path):
    source = document(nvd_payload(), version="fixture-nvd-revision")
    event_context = context(source)
    candidate = enrich_structured_fields(event_context, (source,))[0].candidates[0]
    record = ClaimRecord(
        schema_version=3,
        claim_id=Identifier(value=str(uuid4())),
        subject="event:" + str(event_context.event_id),
        predicate="cvss_signal",
        object_value=candidate.value,
        claim_status="supported",
        claim_origin="structured_source",
        condition_value="unknown",
        freshness="unknown",
        asserted_at=NOW,
        scope=VisibilityScope(visibility="public"),
    )
    scope = AccessScope.for_authenticated_user(str(uuid4()), None, Role.SYSTEM_ADMIN)
    actor = actor_reference_from_payload(
        {
            "credential_kind": "session",
            "user_id": scope.user_id,
            "tenant_id": None,
            "role": scope.role.value,
            "permissions": sorted(scope.permissions),
            "permission_version": scope.permission_version,
            "permissions_digest": _permissions_digest(scope.permissions),
            "resource": "urn:dianzi:api:v1",
            "issued_at": NOW.isoformat(),
            "created_at": NOW.isoformat(),
            "session_hash": "a" * 64,
            "key_id": None,
            "credential_version": None,
        }
    )
    connection = MagicMock(spec=Connection)
    connection.dialect = SimpleNamespace(name="postgresql")
    connection.closed = False
    connection.invalidated = False
    connection.in_transaction.return_value = False
    connection.execution_options.return_value = connection
    storage = ContentStore(tmp_path / "explicit-fixture-objects")
    storage.store_bytes(source.json_payload)
    store = Mock(spec=ContentStorage, wraps=storage)
    reader = build_source_report_reader(connection, actor, scope, store, "fixture")
    claim_id = record.claim_id.value
    revision_id = str(source.revision_id)
    blocks = {block.block_id: block for block in source.blocks}
    links = tuple(
        {
            "claim_id": claim_id,
            "evidence_id": str(uuid4()),
            "block_id": str(span.block_id),
            "revision_id": revision_id,
            "start_offset": blocks[span.block_id].start_offset + span.start_offset,
            "end_offset": blocks[span.block_id].start_offset + span.end_offset,
            "quote": span.quote_text,
            "quote_sha256": span.quote_sha256,
            "coordinate_version": "fulltext_unicode_v1",
            "verified_at": NOW,
            "support_kind": "supports",
            "validation_status": "validated",
            "supports_claim": True,
        }
        for span in candidate.evidence
    )
    request = bridge.StructuredFactProofRequest(
        event_id=event_context.event_id,
        evidence_id=UUID(links[0]["evidence_id"]),
        revision_id=source.revision_id,
    )
    parent = {
        "revision_id": revision_id,
        "source_id": str(source.source_id),
        "document_id": str(source.document_id),
        "content_hash": source.content_sha256,
        "canonical_uri": str(source.canonical_uri),
        "first_observed_at": source.observed_at,
        "is_current": True,
        "size_bytes": len(source.json_payload),
        "visibility": "public",
        "tenant_id": None,
        "parse_status": "parsed",
        "kind": "advisory",
        "normalizer_version": source.source_version,
        "source_metadata": {
            "content_coverage": "full_text",
            "data_mode": "fixture",
            "data_mode_policy_version": "trusted-source-runtime-v1",
        },
    }
    snapshot = bridge._FactInputs(
        event_row={"status": "active", "visibility": "public", "tenant_id": None},
        claim_rows=(
            {
                "claim_id": claim_id,
                "source_revision_id": revision_id,
                "predicate": "cvss_signal",
                "is_current": True,
                "claim_status": "supported",
                "freshness": "unknown",
                "provenance_status": "source_verified",
            },
        ),
        assertions=(
            {
                "claim_id": claim_id,
                "revision_id": revision_id,
                "assertion_id": str(uuid4()),
                "assertion_kind": "structured_source",
                "scoring_authority": "nvd@nist.gov",
                "json_path": "/cve/id",
            },
        ),
        links=links,
        parents=(parent,),
        associations=({"revision_id": revision_id, "active": True, "associated_at": NOW},),
        blocks=tuple(
            {
                "block_id": str(block.block_id),
                "revision_id": revision_id,
                "start_offset": block.start_offset,
            }
            for block in source.blocks
        ),
        dimensions=(),
        identifiers=(("cve", "CVE-2024-37032"),),
        epochs=(("public", 7),),
        truncated=False,
    )
    case = SimpleNamespace(
        reader=reader,
        request=request,
        snapshot=snapshot,
        current=snapshot,
        source=source,
        record=record,
        scope=scope,
        actor=actor,
        connection=connection,
        store=store,
        storage=storage,
    )
    session = MagicMock()
    session.scalar.return_value = "structured_vulnerability"
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    monkeypatch.setattr(bridge, "Session", session_factory)
    monkeypatch.setattr(bridge.event, "listen", Mock())
    monkeypatch.setattr(bridge.event, "remove", Mock())
    auth = Mock(return_value=scope)
    monkeypatch.setattr(bridge, "lock_actor_reference_scope", auth)
    case.auth = auth
    snapshots = iter(("snapshot", "current"))
    monkeypatch.setattr(
        reader, "_read_inputs", lambda session, request: getattr(case, next(snapshots))
    )
    monkeypatch.setattr(reader, "_lock_inputs", Mock())
    monkeypatch.setattr(inputs, "_revision_blocks", lambda session, revision: (source.blocks, True))
    monkeypatch.setattr(bridge.KnowledgeRepository, "get_claim", lambda self, claim: case.record)

    def evidence_response(self, evidence_id):
        link = next(link for link in links if link["evidence_id"] == str(evidence_id))
        block = blocks[UUID(link["block_id"])]
        return EvidenceResponse(
            span_id=evidence_id,
            revision_id=source.revision_id,
            block_id=block.block_id,
            start_offset=link["start_offset"],
            end_offset=link["end_offset"],
            quote_text=link["quote"],
            quote_sha256=link["quote_sha256"],
            locator_kind="json_pointer",
            page_number=None,
            json_pointer=block.json_pointer,
            verified_at=NOW,
            source_uri=source.canonical_uri,
            source_published_at=None,
            source_modified_at=None,
            first_observed_at=source.observed_at,
            ingested_at=NOW,
            data_mode=reader.data_mode,
        )

    monkeypatch.setattr(bridge.KnowledgeReadService, "read_evidence", evidence_response)
    return case


def test_factory_reuses_exact_reader_and_does_not_acquire_connection_or_io(read_case):
    case = read_case
    assert type(case.reader) is bridge.StructuredFactProofReader
    assert case.reader.connection is case.connection
    assert case.reader.actor_reference is case.actor
    assert case.reader.scope is case.scope
    assert case.reader.content_store is case.store
    assert not case.connection.mock_calls
    assert not case.store.mock_calls


def test_normal_read_keeps_typed_value_proof_identity_and_unknown_states(read_case):
    result = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert result.status == "reported"
    fact = result.facts[0]
    assert fact.record == read_case.record
    assert fact.record.object_value.base_score == 9.8
    assert fact.record.condition_value.value == "unknown"
    assert fact.record.freshness.value == "unknown"
    assert fact.primary_assertion_path == "/cve/id"
    assert fact.content_sha256 == read_case.source.content_sha256
    assert fact.report_support == "verified"
    assert result.request is not None and result.request == read_case.request
    assert result.scope_epochs == (("public", 7),)


@pytest.mark.parametrize("mode", ("fixture", "live"))
def test_only_explicit_server_mode_survives_external_metadata(read_case, mode):
    read_case.reader.data_mode = mode
    for parent in read_case.snapshot.parents:
        parent["source_metadata"] = {
            **parent["source_metadata"],
            "data_mode": mode,
            "data_mode_policy_version": "trusted-source-runtime-v1",
        }
    result = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert result.data_mode == mode
    assert all(item.data_mode == mode for item in result.facts[0].supporting_evidence)


def test_missing_hash_object_preserves_saved_value_as_partial(read_case):
    read_case.store.read_verified.side_effect = FileNotFoundError("explicit fixture object missing")
    result = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert result.status == "partial"
    assert "source_object_missing" in result.missing_requirements
    assert result.facts[0].record.object_value.base_score == 9.8
    assert result.facts[0].report_support == "unverified"


def test_matching_quotes_cannot_support_changed_typed_value(read_case):
    read_case.record = read_case.record.model_copy(
        update={
            "object_value": read_case.record.object_value.model_copy(update={"base_score": 1.0})
        }
    )
    result = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert result.status == "partial"
    assert "source_value_mismatch" in result.missing_requirements
    assert result.facts[0].record.object_value.base_score == 1.0
    assert not result.facts[0].supporting_evidence


def test_current_acl_change_aborts_instead_of_returning_earlier_proof(read_case):
    changed = AccessScope.for_authenticated_user(read_case.scope.user_id, None, Role.VIEWER)
    read_case.auth.side_effect = (read_case.scope, changed)
    with pytest.raises(CrossTenantAccessError, match="resource_unavailable"):
        read_case.reader.read(read_case.request, time.monotonic() + 4)


def test_association_withdrawal_downgrades_proof_and_preserves_history(read_case):
    read_case.current = replace(
        read_case.snapshot,
        associations=({**read_case.snapshot.associations[0], "active": False},),
    )
    result = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert result.status == "partial"
    assert "event_document_withdrawn" in result.missing_requirements
    assert result.facts[0].record == read_case.record
    assert result.facts[0].report_support == "unverified"


def test_other_changed_inputs_are_not_disguised_as_association_withdrawal(read_case):
    read_case.current = replace(read_case.snapshot, epochs=(("public", 8),))
    with pytest.raises(bridge.StructuredFactProofChangedError, match="fact_proof_inputs_changed"):
        read_case.reader.read(read_case.request, time.monotonic() + 4)


def test_disputed_fact_remains_conflict_without_replacing_other_saved_values(read_case):
    read_case.record = read_case.record.model_copy(update={"claim_status": ClaimStatus.DISPUTED})
    result = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert result.status == "partial"
    assert result.conflicts == (UUID(read_case.record.claim_id.value),)
    assert "claim_disputed" in result.missing_requirements
    assert result.facts[0].record.object_value.base_score == 9.8


@pytest.mark.parametrize("change", ("closed", "invalidated", "active_transaction", "owner_thread"))
def test_unavailable_caller_connection_is_rejected_before_object_io(read_case, change):
    if change == "active_transaction":
        read_case.connection.in_transaction.return_value = True
    elif change == "owner_thread":
        read_case.reader._owner_thread = -1
    else:
        setattr(read_case.connection, change, True)
    with pytest.raises(ValueError, match="connected_fact_reader_unavailable"):
        read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert not read_case.store.mock_calls


@pytest.mark.parametrize("deadline", (float("nan"), float("inf"), 10.0))
def test_original_five_second_deadline_cannot_be_expanded(read_case, deadline):
    deadline = time.monotonic() + deadline if deadline == 10.0 else deadline
    with pytest.raises(ValueError, match="fact_reader_requires_original_five_second_deadline"):
        read_case.reader.read(read_case.request, deadline)
    assert not read_case.store.mock_calls


def test_three_uuid_request_rejects_extra_scope_and_missing_identity():
    with pytest.raises(ValidationError):
        bridge.StructuredFactProofRequest(event_id=uuid4(), evidence_id=uuid4())
    with pytest.raises(ValidationError):
        bridge.StructuredFactProofRequest(
            event_id=uuid4(), evidence_id=uuid4(), revision_id=uuid4(), tenant_id="external"
        )


def test_replay_rechecks_current_inputs_and_returns_same_saved_fact(monkeypatch, read_case):
    monkeypatch.setattr(
        read_case.reader, "_read_inputs", lambda session, request: read_case.snapshot
    )
    first = read_case.reader.read(read_case.request, time.monotonic() + 4)
    replay = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert replay == first
    assert replay.facts[0].record.claim_id == read_case.record.claim_id
    assert read_case.auth.call_count == 6
    assert read_case.store.read_verified.call_count == 2
    assert not read_case.connection.execute.called


def test_missing_fact_is_no_result_without_a_negative_or_default_score(read_case):
    read_case.snapshot = replace(read_case.snapshot, claim_rows=())
    read_case.current = read_case.snapshot
    result = read_case.reader.read(read_case.request, time.monotonic() + 4)
    assert result.status == "not_found"
    assert result.facts == ()
    assert result.conflicts == ()


@pytest.mark.parametrize("mode", (None, "metadata_live", "unknown"))
def test_factory_requires_existing_explicit_data_mode(read_case, mode):
    with pytest.raises(ValueError, match="current server access scope and explicit data mode"):
        build_source_report_reader(
            read_case.connection, read_case.actor, read_case.scope, read_case.store, mode
        )
    assert not read_case.store.mock_calls
