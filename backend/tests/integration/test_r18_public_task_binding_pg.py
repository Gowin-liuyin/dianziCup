"""Owned PG transaction/owner/lease tests with explicit fixture workflow and QA semantics.

The caller supplies the validated test database. These tests neither start a server
nor run models: actual PG rows, clock, locks, 0031 DDL and rollback are the evidence.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import SecretStr
from sqlalchemy import create_engine, func, insert, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from ai_intel.api.actor_references import (
    InvalidActorReferenceError,
    actor_reference_payload,
    create_actor_reference,
)
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.credentials import SessionCredential
from ai_intel.api.public_task_bindings import (
    PublicTaskBindingConflict,
    PublicTaskBindingService,
    PublicTaskIntegrityError,
    public_task_bindings,
)
from ai_intel.api.question_contracts import QuestionAnswerResponse
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.investigation.workflow_service import (
    investigation_operations,
    investigation_workflows,
)
from ai_intel.knowledge.models import (
    job_payloads,
    job_runs,
    job_transitions,
    metadata,
    outbox_events,
    users,
)
from ai_intel.retrieval.persistence_models import grounded_answers
from ai_intel.workers.jobs import JobLeaseLostError, claim_job, complete_job

pytestmark = pytest.mark.real_pg
ROOT = Path(__file__).resolve().parents[3]


class FixturePgAnswerReader:
    """Actual answer rows with an explicit fixture proof marker; no claim of live grounding."""

    def read_qa_answer_in_session(self, session, scope, answer_id, *, task_id, request_sha256):
        row = (
            session.execute(
                select(grounded_answers)
                .where(
                    grounded_answers.c.answer_id == str(answer_id),
                    grounded_answers.c.user_id == scope.user_id,
                    grounded_answers.c.tenant_id == scope.tenant_id,
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None or row["model_trace"] != {
            "task_id": str(task_id),
            "request_sha256": request_sha256,
            "fixture_proof": "current",
        }:
            raise PublicTaskIntegrityError("fixture_answer_binding_unavailable")
        return QuestionAnswerResponse.model_validate_json(json.dumps(row["response"]))

    def read_stack_check_in_session(self, *args, **kwargs):
        raise AssertionError("stack async producer is not installed")


@dataclass
class TaskCase:
    engine: Engine
    credentials: tuple[SessionCredential, ...]

    def admit(self, session, *, key="fixture-public-key"):
        now = session.scalar(select(func.clock_timestamp()))
        actor = create_actor_reference(session.connection(), self.credentials[0], now)
        event_id = str(UUID("00000000-0000-0000-0000-000000000031"))
        request = {
            "question": "explicit fixture question",
            "event_ids": [event_id],
            "mode": "investigate",
        }
        raw = json.dumps(request).encode()
        job_id = enqueue_job(session, actor.tenant_id, "investigation", raw, now, key)
        owner = session.scalar(
            select(investigation_workflows.c.job_id).where(
                investigation_workflows.c.job_id == job_id
            )
        )
        deadline = now + timedelta(minutes=1)
        if owner is None:
            session.execute(
                insert(investigation_workflows).values(
                    job_id=job_id,
                    owner_user_id=actor.user_id,
                    tenant_id=actor.tenant_id,
                    authorized_role=actor.role.value,
                    actor_reference=actor_reference_payload(actor),
                    graph_version="r14-langgraph-1",
                    input_sha256="a" * 64,
                    input_json={"request": {"question": request["question"], "event_id": event_id}},
                    budget_json={"fixture": True},
                    scope_epochs={"fixture": True},
                    deadline_at=deadline,
                    created_at=now,
                )
            )
        service = PublicTaskBindingService(self.engine, result_reader=FixturePgAnswerReader())
        receipt = service.bind_in_session(
            session,
            job_id=UUID(job_id),
            actor=actor,
            task_type="ask",
            public_request=raw,
            deadline_at=deadline,
        )
        return service, receipt, actor, raw


@pytest.fixture
def task_case(isolated_test_database_url, register_sensitive_failure_value):
    original = make_url(isolated_test_database_url).set(drivername="postgresql+psycopg")
    register_sensitive_failure_value(SecretStr(original.render_as_string(hide_password=False)))
    if original.password:
        register_sensitive_failure_value(SecretStr(original.password))
    schema = "r18_tasks_" + uuid4().hex
    marker = "fixture:r18-public-tasks:" + uuid4().hex
    base = create_engine(
        original, hide_parameters=True, poolclass=NullPool, connect_args={"connect_timeout": 5}
    )
    schema_oid = None
    engine = None
    try:
        with base.begin() as connection:
            assert connection.execute(text("SELECT current_database(),current_user")).one() == (
                original.database,
                original.username,
            )
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f"COMMENT ON SCHEMA {schema} IS '{marker}'")
            schema_oid = connection.scalar(
                text("SELECT oid FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}
            )
        configured = original.update_query_dict(
            {"options": (f"-c search_path={schema} -c statement_timeout=6000 -c lock_timeout=4000")}
        )
        engine = create_engine(
            configured,
            hide_parameters=True,
            poolclass=NullPool,
            connect_args={"connect_timeout": 5},
        )
        tokens = tuple(SessionCredential(SecretStr(secrets.token_urlsafe(32))) for _ in range(3))
        for token in tokens:
            register_sensitive_failure_value(token.token)
        with engine.begin() as connection:
            metadata.create_all(
                connection,
                tables=[
                    users,
                    auth_sessions,
                    job_runs,
                    job_payloads,
                    outbox_events,
                    job_transitions,
                    investigation_workflows,
                    investigation_operations,
                    grounded_answers,
                ],
            )
            spec = importlib.util.spec_from_file_location(
                "public_task_pg_migration",
                ROOT / "backend/migrations/versions/0031_public_task_bindings.py",
            )
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            now = connection.scalar(select(func.clock_timestamp()))
            for index, credential in enumerate(tokens):
                tenant = "fixture-tenant" if index < 2 else "fixture-other-tenant"
                connection.execute(
                    insert(users).values(
                        user_id=f"fixture-user-{index}",
                        username=f"fixture-user-{index}",
                        password_hash="synthetic-not-for-login",
                        tenant_id=tenant,
                        role="analyst",
                        created_at=now,
                    )
                )
                connection.execute(
                    insert(auth_sessions).values(
                        session_hash=hashlib.sha256(
                            credential.token.get_secret_value().encode()
                        ).hexdigest(),
                        user_id=f"fixture-user-{index}",
                        csrf_token="synthetic-not-for-http",
                        issued_at=now,
                        expires_at=now + timedelta(minutes=5),
                        revoked_at=None,
                    )
                )
        yield TaskCase(engine, tokens)
    finally:
        if engine is not None:
            engine.dispose()
        if schema_oid is not None:
            with base.begin() as connection:
                owned = connection.execute(
                    text(
                        "SELECT oid,obj_description(oid,'pg_namespace') FROM pg_namespace "
                        "WHERE nspname=:schema"
                    ),
                    {"schema": schema},
                ).one()
                assert owned == (schema_oid, marker)
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        base.dispose()


def publish_fixture_answer(case, service, session, receipt, actor):
    answer_id = uuid4()
    published = session.scalar(select(func.clock_timestamp()))
    response = {
        "kind": "completed",
        "answer_id": str(answer_id),
        "answer_text": "explicit fixture answer",
        "claims": [],
        "citations": [],
        "limitations": ["fixture semantics; PG storage and fences only"],
        "freshness": "current",
        "data_mode": "fixture",
        "started_at": receipt.admitted_at.isoformat(),
        "completed_at": published.isoformat(),
        "latency_milliseconds": int((published - receipt.admitted_at).total_seconds() * 1000),
    }
    binding = (
        session.execute(
            select(public_task_bindings).where(
                public_task_bindings.c.task_id == str(receipt.task_id)
            )
        )
        .mappings()
        .one()
    )
    session.execute(
        insert(grounded_answers).values(
            answer_id=str(answer_id),
            user_id=actor.user_id,
            tenant_id=actor.tenant_id,
            question_text=binding["public_request_json"]["question"],
            response=response,
            scope_epochs={"fixture": True},
            model_trace={
                "task_id": str(receipt.task_id),
                "request_sha256": binding["request_sha256"],
                "fixture_proof": "current",
            },
            created_at=published,
        )
    )
    service.publish_result_in_session(
        session,
        task_id=receipt.task_id,
        actor=actor,
        worker_id="fixture-worker",
        expected_attempt=1,
        result_kind="qa_answer",
        result_id=answer_id,
    )
    return answer_id


def claimed_case(case):
    with Session(case.engine) as session, session.begin():
        service, receipt, actor, raw = case.admit(session)
    with Session(case.engine) as session, session.begin():
        now = session.scalar(select(func.clock_timestamp()))
        assert claim_job(session, str(receipt.task_id), "fixture-worker", now) is not None
    return service, receipt, actor, raw


def test_caller_rollback_removes_job_owner_payload_outbox_and_public_binding(task_case):
    with Session(task_case.engine) as session:
        session.begin()
        _, receipt, _, _ = task_case.admit(session)
        session.rollback()
    with Session(task_case.engine) as session:
        for stored, column in [
            (job_runs, job_runs.c.job_id),
            (job_payloads, job_payloads.c.job_id),
            (outbox_events, outbox_events.c.job_id),
            (investigation_workflows, investigation_workflows.c.job_id),
            (public_task_bindings, public_task_bindings.c.task_id),
        ]:
            assert (
                session.scalar(
                    select(func.count()).select_from(stored).where(column == str(receipt.task_id))
                )
                == 0
            )


def test_replay_preserves_trace_time_actor_and_one_job_without_new_quota(task_case):
    with Session(task_case.engine) as session, session.begin():
        _, initial, actor, _ = task_case.admit(session)
    with Session(task_case.engine) as session, session.begin():
        _, replay, fresh, _ = task_case.admit(session)
        assert not replay.created and replay.task_id == initial.task_id
        assert replay.trace_id == initial.trace_id and replay.admitted_at == initial.admitted_at
        assert fresh.created_at != actor.created_at
        assert session.scalar(select(func.count()).select_from(job_runs)) == 1
        assert session.scalar(
            select(public_task_bindings.c.actor_reference)
        ) == actor_reference_payload(actor)


@pytest.mark.parametrize("credential_index", [1, 2])
def test_same_tenant_other_owner_and_other_tenant_cannot_read(task_case, credential_index):
    service, receipt, _, _ = claimed_case(task_case)
    with (
        pytest.raises(CrossTenantAccessError),
        Session(task_case.engine) as session,
        session.begin(),
    ):
        actor = create_actor_reference(
            session.connection(),
            task_case.credentials[credential_index],
            session.scalar(select(func.clock_timestamp())),
        )
        service.read_in_session(session, task_id=receipt.task_id, actor=actor)


def test_binding_different_public_payload_conflicts_without_mutating_original(task_case):
    with Session(task_case.engine) as session, session.begin():
        service, receipt, actor, raw = task_case.admit(session)
    with (
        pytest.raises(PublicTaskBindingConflict),
        Session(task_case.engine) as session,
        session.begin(),
    ):
        altered = json.loads(raw) | {"mode": "auto"}
        service.bind_in_session(
            session,
            job_id=receipt.task_id,
            actor=actor,
            task_type="ask",
            public_request=json.dumps(altered).encode(),
            deadline_at=receipt.admitted_at + timedelta(seconds=30),
        )
    with Session(task_case.engine) as session:
        assert (
            session.scalar(select(public_task_bindings.c.public_request_json))["mode"]
            == "investigate"
        )


@pytest.mark.parametrize(
    "change", ["owner", "digest", "delete", "half_locator", "wrong_result_type"]
)
def test_0031_blocks_core_mutation_and_partial_or_wrong_typed_locators(task_case, change):
    _service, receipt, _, _ = claimed_case(task_case)
    with pytest.raises(IntegrityError), Session(task_case.engine) as session, session.begin():
        selected = public_task_bindings.c.task_id == str(receipt.task_id)
        if change == "delete":
            session.execute(public_task_bindings.delete().where(selected))
        else:
            values = {
                "owner": {"owner_user_id": "fixture-user-1"},
                "digest": {"request_sha256": "b" * 64},
                "half_locator": {"result_kind": "qa_answer"},
                "wrong_result_type": {
                    "result_kind": "stack_check",
                    "result_id": str(uuid4()),
                    "result_published_at": session.scalar(select(func.clock_timestamp())),
                },
            }[change]
            session.execute(update(public_task_bindings).where(selected).values(**values))


def test_answer_locator_and_job_completion_commit_in_same_session_and_poll_is_readonly(task_case):
    service, receipt, actor, _ = claimed_case(task_case)
    with Session(task_case.engine) as session, session.begin():
        answer_id = publish_fixture_answer(task_case, service, session, receipt, actor)
        complete_job(
            session,
            str(receipt.task_id),
            "fixture-worker",
            "succeeded",
            session.scalar(select(func.clock_timestamp())),
            expected_attempt=1,
            result_ref="pg:qa_answer:" + str(answer_id),
        )
    with Session(task_case.engine) as session, session.begin():
        fresh = create_actor_reference(
            session.connection(),
            task_case.credentials[0],
            session.scalar(select(func.clock_timestamp())),
        )
        output = service.read_in_session(session, task_id=receipt.task_id, actor=fresh)
        assert output["task"]["status"] == "succeeded" and output["result"]["answer_id"] == str(
            answer_id
        )
        assert output["result"]["data_mode"] == "fixture"
        assert output["result"]["latency_milliseconds"] >= 0
        assert session.scalar(select(func.count()).select_from(grounded_answers)) == 1


def test_publication_rollback_removes_answer_locator_and_keeps_running_job(task_case):
    service, receipt, actor, _ = claimed_case(task_case)
    with Session(task_case.engine) as session:
        session.begin()
        answer_id = publish_fixture_answer(task_case, service, session, receipt, actor)
        session.rollback()
    with Session(task_case.engine) as session:
        assert session.scalar(select(grounded_answers.c.answer_id)) is None
        assert session.scalar(select(public_task_bindings.c.result_kind)) is None
        assert session.scalar(select(job_runs.c.status)) == "running"
        assert str(answer_id) != str(receipt.task_id)


def test_old_attempt_cannot_publish_even_with_current_owner(task_case):
    service, receipt, actor, _ = claimed_case(task_case)
    with Session(task_case.engine) as session, session.begin():
        session.execute(update(job_runs).values(attempt_count=2))
    with pytest.raises(JobLeaseLostError), Session(task_case.engine) as session, session.begin():
        publish_fixture_answer(task_case, service, session, receipt, actor)
    with Session(task_case.engine) as session:
        assert session.scalar(select(public_task_bindings.c.result_kind)) is None
        assert session.scalar(select(grounded_answers.c.answer_id)) is None


def test_successful_scheduling_without_typed_result_is_not_a_completed_answer(task_case):
    service, receipt, actor, _ = claimed_case(task_case)
    with Session(task_case.engine) as session, session.begin():
        complete_job(
            session,
            str(receipt.task_id),
            "fixture-worker",
            "succeeded",
            session.scalar(select(func.clock_timestamp())),
            expected_attempt=1,
            result_ref="pg:investigation:" + str(receipt.task_id),
        )
    with (
        pytest.raises(PublicTaskIntegrityError),
        Session(task_case.engine) as session,
        session.begin(),
    ):
        service.read_in_session(session, task_id=receipt.task_id, actor=actor)


def test_job_lock_wait_uses_database_clock_and_denies_expired_lease(task_case):
    service, receipt, actor, _ = claimed_case(task_case)
    entered = Event()
    with task_case.engine.connect() as holder:
        transaction = holder.begin()
        now = holder.scalar(select(func.clock_timestamp()))
        holder.execute(update(job_runs).values(lease_expires_at=now + timedelta(seconds=0.3)))

        def attempt():
            with (
                pytest.raises(JobLeaseLostError),
                Session(task_case.engine) as session,
                session.begin(),
            ):
                entered.set()
                publish_fixture_answer(task_case, service, session, receipt, actor)

        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(attempt)
            assert entered.wait(2)
            time.sleep(0.4)
            transaction.commit()
            future.result(timeout=3)
    with Session(task_case.engine) as session:
        assert session.scalar(select(public_task_bindings.c.result_kind)) is None


def test_credential_lock_wait_denies_expired_actor_before_result_read(task_case):
    service, receipt, actor, _ = claimed_case(task_case)
    entered = Event()
    with task_case.engine.connect() as holder:
        transaction = holder.begin()
        now = holder.scalar(select(func.clock_timestamp()))
        holder.execute(
            update(auth_sessions)
            .where(auth_sessions.c.user_id == actor.user_id)
            .values(expires_at=now + timedelta(seconds=0.3))
        )

        def attempt():
            with (
                pytest.raises(InvalidActorReferenceError),
                Session(task_case.engine) as session,
                session.begin(),
            ):
                entered.set()
                service.read_in_session(session, task_id=receipt.task_id, actor=actor)

        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(attempt)
            assert entered.wait(2)
            time.sleep(0.4)
            transaction.commit()
            future.result(timeout=3)
