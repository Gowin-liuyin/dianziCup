"""Synthetic current-identity and publication fences; real lock waits remain PG tests."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from test_r18_public_task_bindings import (
    ANSWER_ID,
    TASK_ID,
    actor_fixture,
    binding_fixture,
    read_case,
)

from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.public_task_bindings import (
    PublicTaskBindingConflict,
    PublicTaskBindingService,
    PublicTaskIntegrityError,
)
from ai_intel.domain.access import CrossTenantAccessError


def test_other_credential_locator_of_same_owner_cannot_claim_original_task():
    original = binding_fixture()
    original["actor_reference"] = original["actor_reference"] | {"session_hash": "b" * 64}
    with pytest.raises(CrossTenantAccessError):
        PublicTaskBindingService._owner_matches(original, actor_fixture())


def test_expired_after_reader_resource_lock_does_not_escape_as_completed():
    service, session, actor, _, reader = read_case("succeeded", result=True)
    with patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope") as authentication:
        authentication.side_effect = SessionExpiredError("synthetic lock expiry")
        with pytest.raises(SessionExpiredError):
            service.read_in_session(session, task_id=TASK_ID, actor=actor)
    assert reader.read_qa_answer_in_session.call_count == 1
    session.commit.assert_not_called()


def test_result_reader_cannot_change_the_callers_transaction():
    service, session, actor, _, _ = read_case("succeeded", result=True)
    service._connection.side_effect = [object(), object()]
    with pytest.raises(PublicTaskIntegrityError, match="transaction_changed"):
        service.read_in_session(session, task_id=TASK_ID, actor=actor)


def test_an_existing_locator_cannot_be_rebound_to_a_different_answer():
    service, session, actor, _, _ = read_case("running", result=True)
    session.execute.reset_mock()
    with (
        patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"),
        patch("ai_intel.api.public_task_bindings.require_job_lease"),
        pytest.raises(PublicTaskBindingConflict),
    ):
        service.publish_result_in_session(
            session,
            task_id=TASK_ID,
            actor=actor,
            worker_id="fixture",
            expected_attempt=1,
            result_kind="qa_answer",
            result_id=uuid4(),
        )
    session.execute.assert_not_called()


def test_zero_cas_result_does_not_claim_publication_succeeded():
    service, session, actor, _, _ = read_case("running")
    session.execute.return_value.scalar_one_or_none.return_value = None
    with (
        patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"),
        patch("ai_intel.api.public_task_bindings.require_job_lease"),
        pytest.raises(PublicTaskBindingConflict),
    ):
        service.publish_result_in_session(
            session,
            task_id=TASK_ID,
            actor=actor,
            worker_id="fixture",
            expected_attempt=1,
            result_kind="qa_answer",
            result_id=ANSWER_ID,
        )
    session.commit.assert_not_called()
