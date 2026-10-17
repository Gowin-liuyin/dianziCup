"""Explicit synthetic bindings exercise the public projection without a database or model."""

from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from ai_intel.api.actor_references import (
    actor_reference_payload,
    create_actor_reference,
)
from ai_intel.api.credentials import SessionCredential
from ai_intel.api.public_task_bindings import (
    SCHEMA_VERSION,
    PublicTaskBindingConflict,
    PublicTaskBindingService,
    PublicTaskIntegrityError,
    UnsupportedPublicTaskError,
    project_workflow_steps,
    public_request_digest,
    validate_workflow_request,
)
from ai_intel.api.public_write_adapters import parse_public_ask_request
from ai_intel.api.question_contracts import QuestionAnswerResponse
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.workers.jobs import JobLeaseLostError

NOW = datetime(2026, 10, 17, 3, tzinfo=UTC)
TASK_ID = UUID("00000000-0000-0000-0000-000000000031")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000032")
ANSWER_ID = UUID("00000000-0000-0000-0000-000000000033")
TRACE_ID = UUID("00000000-0000-0000-0000-000000000034")
RAW = json.dumps(
    {"question": "fixture question", "event_ids": [str(EVENT_ID)], "mode": "investigate"}
).encode()


def actor_fixture(at: datetime = NOW):
    token = SecretStr("synthetic-task-binding-session")
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    connection.execute.return_value.mappings.return_value.first.return_value = {
        "session_hash": hashlib.sha256(token.get_secret_value().encode()).hexdigest(),
        "user_id": "fixture-owner",
        "tenant_id": "fixture-tenant",
        "role": "analyst",
        "issued_at": NOW - timedelta(hours=1),
        "expires_at": NOW + timedelta(hours=1),
        "revoked_at": None,
    }
    return create_actor_reference(connection, SessionCredential(token), at)


def binding_fixture():
    payload, digest = public_request_digest(parse_public_ask_request(RAW))
    actor = actor_fixture()
    return {
        "task_id": str(TASK_ID),
        "schema_version": SCHEMA_VERSION,
        "task_type": "ask",
        "owner_user_id": actor.user_id,
        "tenant_id": actor.tenant_id,
        "authorized_role": actor.role.value,
        "actor_reference": actor_reference_payload(actor),
        "public_request_json": payload,
        "request_sha256": digest,
        "trace_id": str(TRACE_ID),
        "admitted_at": NOW,
        "deadline_at": NOW + timedelta(minutes=1),
        "result_kind": None,
        "result_id": None,
        "result_published_at": None,
    }


def answer_fixture(**changes):
    payload = {
        "kind": "completed",
        "answer_id": str(ANSWER_ID),
        "answer_text": "fixture answer",
        "claims": [],
        "citations": [],
        "limitations": ["explicit fixture"],
        "freshness": "current",
        "data_mode": "fixture",
        "started_at": NOW.isoformat(),
        "completed_at": (NOW + timedelta(seconds=1)).isoformat(),
        "latency_milliseconds": 1000,
    }
    payload.update(changes)
    return QuestionAnswerResponse.model_validate_json(json.dumps(payload))


def read_case(status="queued", result=False, rows=()):
    session = MagicMock(spec=Session)
    connection = MagicMock(spec=Connection)
    actor = actor_fixture()
    binding = binding_fixture()
    if result:
        binding.update(
            result_kind="qa_answer",
            result_id=str(ANSWER_ID),
            result_published_at=NOW + timedelta(seconds=1),
        )
    job = {"status": status, "created_at": NOW, "updated_at": NOW + timedelta(seconds=2)}
    reader = MagicMock()
    reader.read_qa_answer_in_session.return_value = answer_fixture()
    service = PublicTaskBindingService(MagicMock(spec=Engine), result_reader=reader)
    service._locked_binding = MagicMock(return_value=(connection, actor_scope(actor), job, binding))
    service._now = MagicMock(return_value=NOW + timedelta(seconds=3))
    service._connection = MagicMock(return_value=connection)
    service._session_fence = MagicMock(side_effect=lambda session: nullcontext())
    session.execute.return_value.mappings.return_value.all.return_value = list(rows)
    return service, session, actor, binding, reader


def actor_scope(actor):
    from ai_intel.domain.access import AccessScope

    return AccessScope(actor.user_id, actor.tenant_id, actor.role, actor.permissions)


def test_digest_is_stable_for_json_order_but_not_a_different_question():
    original = parse_public_ask_request(RAW)
    reordered = parse_public_ask_request(
        json.dumps(dict(reversed(list(json.loads(RAW).items())))).encode()
    )
    changed = parse_public_ask_request(RAW.replace(b"fixture question", b"another question"))
    assert public_request_digest(original) == public_request_digest(reordered)
    assert public_request_digest(original)[1] != public_request_digest(changed)[1]


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "other"),
        ("authorization", "synthetic"),
        ("api_key", "synthetic"),
        ("actor_reference", {}),
        ("mode", "arbitrary"),
    ],
)
def test_public_input_rejects_body_identity_and_secret_fields(field, value):
    raw = json.loads(RAW)
    raw[field] = value
    with pytest.raises(ValueError):
        parse_public_ask_request(json.dumps(raw).encode())


@pytest.mark.parametrize(
    "changes",
    [
        {"question": "different"},
        {"event_ids": []},
        {"event_ids": [str(EVENT_ID), str(uuid4())]},
        {"conversation_id": str(uuid4())},
        {"asset_ids": [str(uuid4())]},
        {"known_at": NOW.isoformat()},
        {"valid_at": NOW.isoformat()},
    ],
)
def test_broader_or_different_public_request_cannot_bind_single_workflow(changes):
    raw = json.loads(RAW)
    raw.update(changes)
    request = parse_public_ask_request(json.dumps(raw).encode())
    with pytest.raises(UnsupportedPublicTaskError):
        validate_workflow_request(
            request, {"request": json.loads(RAW) | {"event_id": str(EVENT_ID)}}
        )


def test_fresh_reference_of_same_credential_matches_original_without_rebinding_it():
    binding = binding_fixture()
    fresh = actor_fixture(NOW + timedelta(seconds=1))
    stored = PublicTaskBindingService._owner_matches(binding, fresh)
    assert stored.created_at == NOW and fresh.created_at != stored.created_at


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_user_id", "same-tenant-other-owner"),
        ("tenant_id", "other-tenant"),
        ("authorized_role", "viewer"),
    ],
)
def test_owner_gate_does_not_trust_only_the_job_tenant(field, value):
    binding = binding_fixture()
    binding[field] = value
    with pytest.raises(CrossTenantAccessError):
        PublicTaskBindingService._owner_matches(binding, actor_fixture())


@pytest.mark.parametrize(
    "status", ["queued", "running", "retry_wait", "waiting_approval", "partial"]
)
def test_pending_and_partial_gets_do_not_produce_an_answer_or_consume_quota(status):
    service, session, actor, _, reader = read_case(status)
    with patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"):
        output = service.read_in_session(session, task_id=TASK_ID, actor=actor)
    assert output["task"]["status"] == status
    assert output["result"] is None and output["error"] is None
    reader.read_qa_answer_in_session.assert_not_called()
    session.commit.assert_not_called()
    assert all(call.args[0].is_select for call in session.execute.call_args_list)


@pytest.mark.parametrize("status", ["failed", "cancelled", "blocked"])
def test_failure_status_is_a_stable_public_problem_without_raw_job_error(status):
    service, session, actor, _, _ = read_case(status)
    with patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"):
        output = service.read_in_session(session, task_id=TASK_ID, actor=actor)
    assert output["result"] is None
    assert output["error"]["error"] == "public_task_" + status
    assert output["error"]["trace_id"] == str(TRACE_ID)


def test_succeeded_without_a_real_typed_locator_is_integrity_error():
    service, session, actor, _, _ = read_case("succeeded")
    with pytest.raises(PublicTaskIntegrityError, match="succeeded_without_result"):
        service.read_in_session(session, task_id=TASK_ID, actor=actor)


def test_running_with_committed_locator_is_rejected_instead_of_premature_completed():
    service, session, actor, _, _ = read_case("running", result=True)
    with pytest.raises(PublicTaskIntegrityError, match="pending_has_result"):
        service.read_in_session(session, task_id=TASK_ID, actor=actor)


def test_succeeded_returns_only_frozen_public_answer_and_original_request_digest():
    service, session, actor, binding, reader = read_case("succeeded", result=True)
    with patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"):
        output = service.read_in_session(session, task_id=TASK_ID, actor=actor)
    assert output["result"] == answer_fixture().model_dump(mode="json")
    assert set(output) == {
        "task",
        "result",
        "error",
        "completed_steps",
        "pending_steps",
        "failed_steps",
    }
    reader.read_qa_answer_in_session.assert_called_once_with(
        session,
        actor_scope(actor),
        ANSWER_ID,
        task_id=TASK_ID,
        request_sha256=binding["request_sha256"],
    )
    assert output["task"]["poll_uri"] == "/api/v1/tasks/" + str(TASK_ID)


@pytest.mark.parametrize(
    "changes",
    [
        {"answer_id": str(uuid4())},
        {"freshness": "stale"},
        {"started_at": (NOW + timedelta(milliseconds=1)).isoformat()},
        {"latency_milliseconds": 2},
        {"completed_at": (NOW + timedelta(seconds=20)).isoformat()},
    ],
)
def test_answer_id_currentproof_and_complete_latency_are_not_fabricated(changes):
    service, session, actor, _, reader = read_case("succeeded", result=True)
    reader.read_qa_answer_in_session.return_value = answer_fixture(**changes)
    with pytest.raises(PublicTaskIntegrityError, match="answer_binding_invalid"):
        service.read_in_session(session, task_id=TASK_ID, actor=actor)


def test_workflow_result_shape_cannot_be_used_as_question_answer():
    service, session, actor, _, reader = read_case("succeeded", result=True)
    reader.read_qa_answer_in_session.return_value = {"status": "partial", "answer": {}}
    with pytest.raises(PublicTaskIntegrityError, match="answer_type_invalid"):
        service.read_in_session(session, task_id=TASK_ID, actor=actor)


def test_answer_clock_is_read_after_result_lock_wait():
    service, session, actor, _, reader = read_case("succeeded", result=True)
    service._now.return_value = NOW

    def read_after_lock(*args, **kwargs):
        service._now.return_value = NOW + timedelta(seconds=3)
        return answer_fixture()

    reader.read_qa_answer_in_session.side_effect = read_after_lock
    with patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"):
        result = service.read_in_session(session, task_id=TASK_ID, actor=actor)
    assert result["result"]["answer_id"] == str(ANSWER_ID)


def test_step_groups_use_receipts_and_keep_partial_pending_not_completed():
    rows = [
        {"kind": "node", "role": "qa", "status": "succeeded"},
        {"kind": "model", "role": "critic", "status": "partial"},
        {"kind": "node", "role": "reporter", "status": "succeeded"},
        {"kind": "node", "role": "reporter", "status": "failed"},
    ]
    assert project_workflow_steps(rows) == (["node:qa"], ["model:critic"], ["node:reporter"])


@pytest.mark.parametrize(
    "field,value", [("kind", []), ("role", "authorization"), ("status", "unknown")]
)
def test_untrusted_step_fields_are_not_echoed(field, value):
    row = {"kind": "node", "role": "qa", "status": "succeeded"} | {field: value}
    with pytest.raises(PublicTaskIntegrityError):
        project_workflow_steps([row])


def test_ports_reject_missing_transaction_and_other_engine_before_connection():
    engine, other = MagicMock(spec=Engine), MagicMock(spec=Engine)
    service = PublicTaskBindingService(engine)
    session = MagicMock(spec=Session)
    session.in_transaction.return_value = False
    with pytest.raises(ValueError, match="caller transaction"):
        service._connection(session)
    session.in_transaction.return_value = True
    session.get_bind.return_value = other
    with pytest.raises(ValueError, match="service engine"):
        service._connection(session)
    session.connection.assert_not_called()


def test_stack_binding_is_explicitly_unsupported_and_has_no_side_effects():
    service, session, actor, _, reader = read_case()
    with pytest.raises(UnsupportedPublicTaskError, match="stack_task_unsupported"):
        service.bind_in_session(
            session,
            job_id=TASK_ID,
            actor=actor,
            task_type="stack_check",
            public_request=b"{}",
            deadline_at=NOW + timedelta(seconds=30),
        )
    session.execute.assert_not_called()
    reader.read_stack_check_in_session.assert_not_called()


def test_replay_retains_original_trace_and_admission_time_and_does_not_insert():
    service, session, actor, binding, _ = read_case()
    owner = binding | {
        "input_json": {"request": {"question": "fixture question", "event_id": str(EVENT_ID)}}
    }
    job = {"job_type": "investigation"}
    service._lock_job = MagicMock(return_value=(MagicMock(), actor_scope(actor), job))
    service._lock_workflow = MagicMock(return_value=owner)
    session.execute.return_value.mappings.return_value.first.return_value = binding
    with patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"):
        receipt = service.bind_in_session(
            session,
            job_id=TASK_ID,
            actor=actor,
            task_type="ask",
            public_request=RAW,
            deadline_at=NOW + timedelta(seconds=30),
        )
    assert not receipt.created and receipt.trace_id == TRACE_ID and receipt.admitted_at == NOW
    assert all(call.args[0].is_select for call in session.execute.call_args_list)


def test_different_public_payload_on_existing_binding_is_conflict():
    service, session, actor, binding, _ = read_case()
    service._lock_job = MagicMock(
        return_value=(MagicMock(), actor_scope(actor), {"job_type": "investigation"})
    )
    service._lock_workflow = MagicMock(
        return_value=binding
        | {"input_json": {"request": {"question": "fixture question", "event_id": str(EVENT_ID)}}}
    )
    session.execute.return_value.mappings.return_value.first.return_value = binding | {
        "request_sha256": "0" * 64
    }
    with pytest.raises(PublicTaskBindingConflict):
        service.bind_in_session(
            session,
            job_id=TASK_ID,
            actor=actor,
            task_type="ask",
            public_request=RAW,
            deadline_at=NOW + timedelta(seconds=30),
        )


@pytest.mark.parametrize("fence", ["old_attempt", "locked_deadline", "final_lease"])
def test_publication_rechecks_lease_and_deadline_and_rolls_back_without_locator(fence):
    service, session, actor, _, _ = read_case("running")
    session.execute.reset_mock()
    if fence == "locked_deadline":
        service._now.return_value = NOW + timedelta(minutes=1)
    with (
        patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"),
        patch("ai_intel.api.public_task_bindings.require_job_lease") as lease,
    ):
        if fence == "old_attempt":
            lease.side_effect = JobLeaseLostError("synthetic old attempt")
        if fence == "final_lease":
            lease.side_effect = [None, JobLeaseLostError("synthetic expired lease")]
        with pytest.raises(JobLeaseLostError):
            service.publish_result_in_session(
                session,
                task_id=TASK_ID,
                actor=actor,
                worker_id="fixture-worker",
                expected_attempt=1,
                result_kind="qa_answer",
                result_id=ANSWER_ID,
            )
    session.execute.assert_not_called()


def test_publication_sets_locator_once_but_never_completes_job_or_commits():
    service, session, actor, _, _ = read_case("running")
    session.execute.return_value.scalar_one_or_none.return_value = str(TASK_ID)
    with (
        patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"),
        patch("ai_intel.api.public_task_bindings.require_job_lease") as lease,
    ):
        service.publish_result_in_session(
            session,
            task_id=TASK_ID,
            actor=actor,
            worker_id="fixture-worker",
            expected_attempt=1,
            result_kind="qa_answer",
            result_id=ANSWER_ID,
        )
    assert lease.call_count == 2
    statement = session.execute.call_args.args[0]
    assert statement.is_update and statement.table.name == "public_task_bindings"
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
