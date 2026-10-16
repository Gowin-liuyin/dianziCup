"""Real PG boundary regressions; synthetic receipts never claim model or live evidence."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from ai_intel.answering.conversation_context import ConversationContextService
from ai_intel.answering.conversation_contracts import ConversationFailure
from ai_intel.answering.conversation_models import qa_conversation_turns, qa_conversations
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.knowledge.models import users
from ai_intel.knowledge.persistence_models import events
from ai_intel.retrieval.persistence_models import grounded_answers
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from tests.integration.test_r12_conversation_assets_pg import import_snapshot
from tests.integration.test_r12_conversation_context_pg import admit
from tests.r12_conversation_fixtures import context_identity as context_identity
from tests.r12_conversation_fixtures import conversation_database as conversation_database
from tests.r12_conversation_fixtures import record_synthetic_completion
from tests.r12_hybrid_fixtures import seed_fact

pytestmark = pytest.mark.real_pg


def expire_reservation(engine, turn):
    with engine.begin() as connection:
        trace = connection.scalar(
            select(grounded_answers.c.model_trace).where(
                grounded_answers.c.answer_id == str(turn.answer_id)
            )
        )
        trace["reservation_expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        connection.execute(
            update(grounded_answers)
            .where(grounded_answers.c.answer_id == str(turn.answer_id))
            .values(model_trace=trace)
        )


@pytest.mark.parametrize("parent_state", ["failed", "completed"])
def test_pg_parent_without_bound_object_cannot_bind_pronoun(context_identity, parent_state):
    engine, _auth, scope, token, _login = context_identity
    turn = admit(context_identity)
    service = ConversationContextService(engine)
    if parent_state == "completed":
        record_synthetic_completion(service, engine, scope, token, turn)
    else:
        service.fail_turn(
            scope,
            turn.turn_id,
            reservation_id=turn.reservation_id,
            reason_code="synthetic_failure",
            session_token=token,
        )
    with pytest.raises(ConversationFailure, match="reference_ambiguous"):
        admit(
            context_identity,
            key="unbound-child",
            conversation=turn.conversation_id,
            version=turn.conversation_version,
            question="它的修复是什么？",
        )
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1


def test_pg_rejected_clarification_keeps_expiration_and_nonce_replay(context_identity):
    engine, _auth, scope, token, _login = context_identity
    turn = admit(context_identity)
    expire_reservation(engine, turn)
    with pytest.raises(ConversationFailure, match="reference_ambiguous"):
        admit(
            context_identity,
            key="unbound-expired-child",
            conversation=turn.conversation_id,
            version=turn.conversation_version,
            question="它的修复是什么？",
        )
    replay = admit(context_identity)
    assert replay.replayed and replay.state == "expired"
    assert replay.answer_id == turn.answer_id
    assert [item.state for item in replay.history] == ["pending", "expired"]
    assert (
        ConversationContextService(engine).read_history(scope, turn.turn_id, session_token=token)
        == replay.history
    )
    with engine.connect() as connection:
        assert connection.scalar(select(qa_conversations.c.active_turn_id)) is None
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1


def test_pg_expired_slot_allows_exact_current_version_once(context_identity):
    engine = context_identity[0]
    turn = admit(context_identity)
    expire_reservation(engine, turn)
    with pytest.raises(ConversationFailure, match="conversation_version_conflict"):
        admit(context_identity, key="stale-child", conversation=turn.conversation_id, version=0)
    followup = admit(
        context_identity,
        key="current-child",
        conversation=turn.conversation_id,
        version=turn.conversation_version,
    )
    replay = admit(
        context_identity,
        key="current-child",
        conversation=turn.conversation_id,
        version=turn.conversation_version,
    )
    assert replay.replayed and replay.turn_id == followup.turn_id
    assert followup.turn_number == 2
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 2


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_pg_turn_metadata_is_immutable(context_identity, operation):
    engine = context_identity[0]
    turn = admit(context_identity)
    with (
        pytest.raises(IntegrityError, match="conversation turns are immutable"),
        engine.begin() as connection,
    ):
        if operation == "update":
            statement = update(qa_conversation_turns).values(context_sha256="a" * 64)
        else:
            statement = delete(qa_conversation_turns)
        connection.execute(statement.where(qa_conversation_turns.c.turn_id == turn.turn_id))
    with engine.connect() as connection:
        assert connection.scalar(select(qa_conversation_turns.c.context_sha256)) == (
            turn.context.context_sha256
        )


def test_pg_legacy_parent_identity_mismatch_fails_closed(context_identity):
    """The owned runner explicitly disables the guard to inject legacy corruption."""
    engine, _auth, scope, token, _login = context_identity
    fact = seed_fact(engine, "Synthetic current source.", cve="CVE-2026-10001")
    turn = admit(context_identity, event_ids=(UUID(fact["event_id"]),))
    service = ConversationContextService(engine)
    record_synthetic_completion(service, engine, scope, token, turn)
    with engine.begin() as connection:
        context = connection.scalar(select(qa_conversation_turns.c.resolved_context))
        context["conversation_id"] = str(uuid4())
        canonical = {name: value for name, value in context.items() if name != "context_sha256"}
        digest = hashlib.sha256(
            json.dumps(
                canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
        context["context_sha256"] = digest
        connection.execute(
            update(qa_conversation_turns).values(resolved_context=context, context_sha256=digest)
        )
    for operation in (
        lambda: service.read_turn(scope, turn.turn_id, session_token=token),
        lambda: admit(
            context_identity,
            key="child-with-valid-hash-wrong-identity",
            conversation=turn.conversation_id,
            version=turn.conversation_version,
            question="它的来源是什么？",
        ),
    ):
        with pytest.raises(ConversationFailure, match="context_integrity_unavailable"):
            operation()
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1


def test_pg_inactive_history_and_replay_are_stale_but_child_has_no_answer(context_identity):
    engine, _auth, scope, token, _login = context_identity
    fact = seed_fact(engine, "Synthetic archived source.", cve="CVE-2026-10001")
    turn = admit(context_identity, event_ids=(UUID(fact["event_id"]),))
    service = ConversationContextService(engine)
    record_synthetic_completion(service, engine, scope, token, turn)
    with engine.begin() as connection:
        connection.execute(
            update(events).where(events.c.event_id == fact["event_id"]).values(status="withdrawn")
        )
    restored = service.read_turn(scope, turn.turn_id, session_token=token)
    replay = admit(context_identity, event_ids=(UUID(fact["event_id"]),))
    assert restored.context == replay.context == turn.context
    assert restored.reference_freshness == replay.reference_freshness == "stale"
    with pytest.raises(ConversationFailure, match="reference_no_longer_visible"):
        admit(
            context_identity,
            key="withdrawn-child",
            conversation=turn.conversation_id,
            version=turn.conversation_version,
            question="它的修复是什么？",
        )
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1


def test_pg_history_and_parent_reauthorize_current_event_acl(context_identity):
    engine, _auth, scope, token, _login = context_identity
    fact = seed_fact(engine, "Synthetic formerly public source.", cve="CVE-2026-10001")
    turn = admit(context_identity, event_ids=(UUID(fact["event_id"]),))
    service = ConversationContextService(engine)
    record_synthetic_completion(service, engine, scope, token, turn)
    with engine.begin() as connection:
        connection.execute(
            update(events)
            .where(events.c.event_id == fact["event_id"])
            .values(visibility="tenant", tenant_id="tenant-b", scope_key="tenant:tenant-b")
        )
    with pytest.raises(CrossTenantAccessError):
        service.read_turn(scope, turn.turn_id, session_token=token)
    with pytest.raises(CrossTenantAccessError):
        admit(
            context_identity,
            key="hidden-parent-child",
            conversation=turn.conversation_id,
            version=turn.conversation_version,
        )
    assert [
        item.state for item in service.read_history(scope, turn.turn_id, session_token=token)
    ] == [
        "pending",
        "completed",
    ]


def test_pg_snapshot_history_stays_frozen_and_followup_reads_current_snapshot(context_identity):
    engine, _auth, _scope, _token, login = context_identity
    scope, token = login(role=Role.TENANT_ADMIN)
    asset = import_snapshot(engine, scope)
    service = ConversationContextService(engine)
    turn = service.admit(
        QuestionRequest(
            question="Synthetic asset impact", asset_ids=(UUID(asset.asset_id),), mode="library"
        ),
        scope,
        "frozen-asset-context",
        conversation_version=None,
        session_token=token,
    )
    record_synthetic_completion(service, engine, scope, token, turn)
    changed = import_snapshot(engine, scope, asset_id=asset.asset_id, version="1.1")
    restored = service.read_turn(scope, turn.turn_id, session_token=token)
    assert restored.context == turn.context and restored.reference_freshness == "stale"
    followup = service.admit(
        QuestionRequest(
            question="它的影响是什么？", conversation_id=turn.conversation_id, mode="library"
        ),
        scope,
        "current-asset-context",
        conversation_version=turn.conversation_version,
        session_token=token,
    )
    assert followup.context.asset_snapshot_refs[0].snapshot_id == UUID(changed.snapshot.snapshot_id)
    assert followup.context.reference_turn_ids == (turn.turn_id,)


def test_pg_history_does_not_restore_revoked_asset_read_permission(context_identity):
    engine, _auth, _scope, _token, login = context_identity
    scope, token = login(role=Role.TENANT_ADMIN)
    asset = import_snapshot(engine, scope)
    service = ConversationContextService(engine)
    turn = service.admit(
        QuestionRequest(
            question="Synthetic asset history", asset_ids=(UUID(asset.asset_id),), mode="library"
        ),
        scope,
        "asset-permission-history",
        conversation_version=None,
        session_token=token,
    )
    record_synthetic_completion(service, engine, scope, token, turn)
    with engine.begin() as connection:
        connection.execute(
            update(users).where(users.c.user_id == scope.user_id).values(role=Role.VIEWER.value)
        )
    viewer = AccessScope.for_authenticated_user(scope.user_id, scope.tenant_id, Role.VIEWER)
    with pytest.raises(PermissionDeniedError):
        service.read_turn(viewer, turn.turn_id, session_token=token)
    with pytest.raises(PermissionDeniedError):
        service.admit(
            QuestionRequest(
                question="Its current impact", conversation_id=turn.conversation_id, mode="library"
            ),
            viewer,
            "asset-permission-child",
            conversation_version=turn.conversation_version,
            session_token=token,
        )
