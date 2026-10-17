"""Publication fixture fences and real SQLite routing boundaries; no PG substitute claims."""

from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, Table, Text, create_engine, event, select, text
from sqlalchemy.orm import Session
from test_r18_public_task_bindings import (
    ANSWER_ID,
    NOW,
    TASK_ID,
    actor_fixture,
    actor_scope,
    answer_fixture,
    binding_fixture,
    read_case,
)

from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.public_task_bindings import (
    PublicTaskBindingConflict,
    PublicTaskBindingService,
    PublicTaskIntegrityError,
    public_task_bindings,
)
from ai_intel.knowledge.models import job_runs, users
from ai_intel.retrieval.persistence_models import grounded_answers
from ai_intel.workers.jobs import JobLeaseLostError


@pytest.mark.parametrize("replay", [True, False])
@pytest.mark.parametrize("expired", ["lease", "deadline", "actor"])
def test_every_publication_path_rechecks_reader_wait_fences(replay, expired):
    service, session, actor, binding, _ = read_case("running", result=replay)
    service._now.side_effect = [NOW + timedelta(seconds=3), NOW + timedelta(minutes=2)]

    def require_lease(_session, _task, _worker, at, *, expected_attempt):
        if expired == "lease" and at >= binding["deadline_at"]:
            raise JobLeaseLostError("fixture lease expired during reader wait")

    failure = SessionExpiredError if expired == "actor" else JobLeaseLostError
    with (
        patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope") as authentication,
        patch("ai_intel.api.public_task_bindings.require_job_lease", side_effect=require_lease),
        pytest.raises(failure),
    ):
        if expired == "actor":
            authentication.side_effect = [
                None,
                SessionExpiredError("fixture current actor expired"),
            ]
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


def test_same_locator_replay_keeps_locator_but_still_runs_both_fences():
    service, session, actor, _, reader = read_case("running", result=True)
    with (
        patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope") as authentication,
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
    assert authentication.call_count == 2 and lease.call_count == 2
    reader.read_qa_answer_in_session.assert_called_once()
    session.execute.assert_not_called()


def test_cross_locator_conflict_never_calls_reader_or_writes_after_initial_fence():
    service, session, actor, _, reader = read_case("running", result=True)
    with (
        patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"),
        patch("ai_intel.api.public_task_bindings.require_job_lease") as lease,
        pytest.raises(PublicTaskBindingConflict),
    ):
        service.publish_result_in_session(
            session,
            task_id=TASK_ID,
            actor=actor,
            worker_id="fixture-worker",
            expected_attempt=1,
            result_kind="qa_answer",
            result_id=uuid4(),
        )
    lease.assert_called_once()
    reader.read_qa_answer_in_session.assert_not_called()
    session.execute.assert_not_called()


@pytest.mark.parametrize("stored_table", [public_task_bindings, job_runs, users, grounded_answers])
def test_registered_table_routing_is_rejected_before_sql(stored_table):
    engine, other = create_engine("sqlite://"), create_engine("sqlite://")
    other_sql = []
    event.listen(other, "before_cursor_execute", lambda *args: other_sql.append(True))
    try:
        with Session(bind=engine, binds={stored_table: other}) as session, session.begin():
            assert session.get_bind() is engine
            with pytest.raises(ValueError, match="service engine"):
                PublicTaskBindingService(engine)._connection(session)
        assert not other_sql
    finally:
        engine.dispose()
        other.dispose()


@pytest.mark.parametrize("port", ["bind", "read", "publish"])
def test_all_public_ports_install_routing_fence_before_business_work(port):
    engine, other = create_engine("sqlite://"), create_engine("sqlite://")
    service = PublicTaskBindingService(engine)
    try:
        with (
            Session(bind=engine, binds={public_task_bindings: other}) as session,
            session.begin(),
            pytest.raises(ValueError, match="service engine"),
        ):
            if port == "bind":
                service.bind_in_session(
                    session,
                    job_id=TASK_ID,
                    actor=actor_fixture(),
                    task_type="ask",
                    public_request=b"{}",
                    deadline_at=NOW + timedelta(minutes=1),
                )
            elif port == "read":
                service.read_in_session(session, task_id=TASK_ID, actor=actor_fixture())
            else:
                service.publish_result_in_session(
                    session,
                    task_id=TASK_ID,
                    actor=actor_fixture(),
                    worker_id="fixture",
                    expected_attempt=1,
                    result_kind="qa_answer",
                    result_id=ANSWER_ID,
                )
    finally:
        engine.dispose()
        other.dispose()


@pytest.mark.parametrize("bind_connection", [False, True])
def test_engine_and_caller_connection_stay_in_the_exact_transaction(bind_connection):
    engine = create_engine("sqlite://")
    service = PublicTaskBindingService(engine)
    try:
        with engine.connect() as connection, connection.begin():
            binding = connection if bind_connection else engine
            with Session(binding) as session, session.begin():
                with service._session_fence(session):
                    authorized = service._connection(session)
                    transaction = authorized.get_transaction()
                    assert session.scalar(select(1)) == 1
                    assert session.scalar(text("SELECT 2")) == 2
                    assert session.connection() is authorized
                    assert authorized.get_transaction() is transaction
                assert not session.dispatch.do_orm_execute
                assert not session.dispatch.after_begin
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind", ["statement", "explicit_connection"])
def test_unregistered_reader_table_cannot_reach_another_engine(kind):
    engine, other = create_engine("sqlite://"), create_engine("sqlite://")
    private_table = Table("fixture_reader_row", MetaData(), Column("value", Text))
    private_table.create(other)
    other_sql = []
    event.listen(other, "before_cursor_execute", lambda *args: other_sql.append(True))
    service = PublicTaskBindingService(engine)
    try:
        with Session(bind=engine, binds={private_table: other}) as session, session.begin():
            with (
                pytest.raises(ValueError, match="engine and connection"),
                service._session_fence(session),
            ):
                if kind == "statement":
                    session.execute(select(private_table))
                else:
                    session.connection(bind_arguments={"bind": other}).execute(
                        select(private_table)
                    )
            assert not session.dispatch.do_orm_execute
            assert not session.dispatch.after_begin
        assert not other_sql
    finally:
        engine.dispose()
        other.dispose()


def test_same_engine_other_connection_is_rejected_before_its_sql():
    engine = create_engine("sqlite://")
    private_table = Table("fixture_reader_same_engine", MetaData(), Column("value", Text))
    service = PublicTaskBindingService(engine)
    try:
        with (
            engine.connect() as other_connection,
            Session(bind=engine, binds={private_table: other_connection}) as session,
            session.begin(),
        ):
            with (
                pytest.raises(ValueError, match="engine and connection"),
                service._session_fence(session),
            ):
                session.execute(select(private_table))
            assert not other_connection.in_transaction()
    finally:
        engine.dispose()


def test_same_connection_reopened_session_transaction_is_rejected():
    engine = create_engine("sqlite://")
    service = PublicTaskBindingService(engine)
    try:
        with engine.connect() as connection, connection.begin(), Session(connection) as session:
            session.begin()
            with (
                pytest.raises(PublicTaskIntegrityError, match="transaction_changed"),
                service._session_fence(session),
            ):
                session.commit()
                session.begin()
            assert connection.in_transaction()
            session.rollback()
            assert not session.dispatch.do_orm_execute
            assert not session.dispatch.after_begin
    finally:
        engine.dispose()


def test_trusted_reader_query_is_checked_inside_actual_public_get():
    engine, other = create_engine("sqlite://"), create_engine("sqlite://")
    operation_table = Table(
        "investigation_operations",
        MetaData(),
        Column("job_id", Text),
        Column("kind", Text),
        Column("role", Text),
        Column("status", Text),
    )
    private_table = Table("fixture_qa_proof", MetaData(), Column("value", Text))
    operation_table.create(engine)
    private_table.create(other)
    other_sql = []
    event.listen(other, "before_cursor_execute", lambda *args: other_sql.append(True))
    actor, binding = actor_fixture(), binding_fixture()
    binding.update(
        result_kind="qa_answer",
        result_id=str(ANSWER_ID),
        result_published_at=NOW + timedelta(seconds=1),
    )
    reader = MagicMock()

    def read(session, *args, **kwargs):
        session.execute(select(private_table))
        return answer_fixture()

    reader.read_qa_answer_in_session.side_effect = read
    service = PublicTaskBindingService(engine, result_reader=reader)
    try:
        with Session(bind=engine, binds={private_table: other}) as session, session.begin():
            connection = session.connection()
            service._locked_binding = MagicMock(
                return_value=(
                    connection,
                    actor_scope(actor),
                    {
                        "status": "succeeded",
                        "created_at": NOW,
                        "updated_at": NOW + timedelta(seconds=2),
                    },
                    binding,
                )
            )
            with pytest.raises(ValueError, match="engine and connection"):
                service.read_in_session(session, task_id=TASK_ID, actor=actor)
        assert not other_sql
    finally:
        engine.dispose()
        other.dispose()
