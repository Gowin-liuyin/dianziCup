"""Real isolated PG/checkpoints with explicit synthetic source/model fixtures, never live."""

import hashlib
import json
import os
import secrets
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r10_evidence_graph_pg import VERSION, publish_event, publish_fact

from ai_intel.api.actor_references import InvalidActorReferenceError, create_actor_reference
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.authentication import Principal, SessionExpiredError
from ai_intel.api.credential_models import api_keys
from ai_intel.api.credentials import ApiKeyCredential, SessionCredential
from ai_intel.assets.inventory import InventoryService
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.models.generation import GenerationClient
from ai_intel.infrastructure.network import FetchResult
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.checkpoint_runtime import setup_checkpoint_schema
from ai_intel.investigation.graph_contracts import InvestigationRequest, WorkflowBudget
from ai_intel.investigation.tool_contracts import ReadEvidenceArguments, ReadEvidenceCall
from ai_intel.investigation.tool_gateway import BudgetLimits, PostgresEvidenceReader, ToolGateway
from ai_intel.investigation.workflow_service import (
    WORKFLOW_TABLES,
    InvestigationWorkflowService,
    WorkflowBusyError,
    investigation_operations,
    investigation_workflows,
)
from ai_intel.knowledge.models import job_runs, scope_epochs, users
from ai_intel.workers.executor import JobExecutionContext
from ai_intel.workers.jobs import claim_job

pytestmark = pytest.mark.real_pg


@pytest.fixture
def workflow_resources(isolated_test_database_url, register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    run_id = os.environ.get("DIANZI_TEST_RUN_ID", "")
    if not run_id:
        raise pytest.UsageError("blocked: DIANZI_TEST_RUN_ID required")
    url = make_url(isolated_test_database_url)
    schema = "test_r14_workflow_" + uuid4().hex
    base = create_engine(
        url, poolclass=NullPool, connect_args={"connect_timeout": 5}, hide_parameters=True
    )
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped_url = url.update_query_dict(
        {
            "options": f"-c search_path={schema} -c statement_timeout=10000 -c lock_timeout=5000",
            "connect_timeout": "5",
        }
    )
    engine = create_engine(scoped_url, poolclass=NullPool, hide_parameters=True)
    dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
    register_sensitive_failure_value(SecretStr(dsn))
    try:
        run_migrations(scoped_url.render_as_string(hide_password=False))
        for table in WORKFLOW_TABLES:
            table.create(engine, checkfirst=True)
        api_keys.create(engine, checkfirst=True)
        setup_checkpoint_schema(dsn, schema, controlled_deployment=True)
        yield engine, dsn, schema
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def principal_session(engine, register, tenant="fixture-owner", role="analyst"):
    user_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    register(SecretStr(token))
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                user_id=user_id,
                username="fixture-workflow-" + uuid4().hex,
                password_hash="fixture-unused",
                tenant_id=tenant,
                role=role,
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
    return user_id, token


def evidence_request(engine, tmp_path, *, strategy="B2b", scope=None):
    event_id = uuid4()
    submission = publish_fact(engine, tmp_path, event_id, VERSION, scope=scope)
    publish_event(engine, event_id, [submission], scope=scope)
    evidence_id = UUID(submission.evidence_links[0].evidence_id.value)
    return InvestigationRequest(
        question="这份合成公告中的受影响版本范围是什么？",
        event_id=event_id,
        evidence_refs=(
            ReadEvidenceArguments(
                event_id=event_id,
                evidence_id=evidence_id,
                revision_id=UUID(submission.revision_id.value),
            ),
        ),
        strategy=strategy,
    )


def fixture_factory(monkeypatch, request, calls, *, planner_choice=None, unsupported=False):
    def factory(limits):
        client = GenerationClient(
            "deepseek_openai",
            "deepseek-flash",
            SecretStr("synthetic-r14-workflow-credential"),
            limits=limits,
        )

        def post(url, body, *, protocol_headers, deadline):
            wire = json.loads(body)
            calls.append(wire)
            message = wire["messages"][0]["content"]
            evidence_id = str(request.evidence_refs[0].evidence_id)
            if "candidate_action_id" in message:
                output = {
                    "candidate_action_id": planner_choice or "read_evidence:" + evidence_id,
                    "reason_code": "fill_current_support",
                    "short_reason": "核验指定合成来源",
                }
            elif "verdicts" in message:
                output = {
                    "verdicts": [
                        {
                            "claim_index": 1,
                            "verdict": "unsupported" if unsupported else "supported",
                            "numbers_match": True,
                            "states_preserved": True,
                            "suggestion_only": False,
                        }
                    ]
                }
            else:
                output = {
                    "claims": [
                        {
                            "text": VERSION["raw_expression"],
                            "kind": "source_fact",
                            "support_ids": [evidence_id],
                        }
                    ],
                    "citations": [{"evidence_id": evidence_id, "quote": VERSION["raw_expression"]}],
                }
            payload = {
                "id": "synthetic-workflow-call-" + str(len(calls)),
                "object": "chat.completion",
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(output)},
                    }
                ],
            }
            return FetchResult(url, 200, "application/json", json.dumps(payload).encode())

        monkeypatch.setattr(client._gateway, "post_json", post)
        return client

    return factory


def service(resources, token, factory=None):
    engine, dsn, schema = resources
    return InvestigationWorkflowService(
        engine,
        SessionCredential(SecretStr(token)),
        dsn,
        schema,
        data_mode="fixture",
        model_factory=factory,
        model_provider="deepseek_openai" if factory else None,
        model_version="deepseek-flash" if factory else None,
    )


def claim(engine, job_id):
    with Session(engine) as session, session.begin():
        row = claim_job(session, str(job_id), "fixture-r14-worker", datetime.now(UTC))
        assert row is not None
        return JobExecutionContext(
            str(job_id), "fixture-r14-worker", row["attempt_count"], row["tenant_id"]
        )


def test_real_pg_enqueue_never_claims_an_existing_job_without_owner_binding(
    workflow_resources, tmp_path, register_sensitive_failure_value, monkeypatch
):
    from ai_intel.infrastructure.outbox import enqueue_job
    from ai_intel.investigation import workflow_service

    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)

    def existing_ownerless_job(session, tenant, kind, payload, now, key):
        return enqueue_job(session, tenant, kind, payload, now - timedelta(minutes=1), key)

    monkeypatch.setattr(workflow_service, "enqueue_job", existing_ownerless_job)
    with pytest.raises(CrossTenantAccessError):
        service(workflow_resources, token).enqueue(
            request, WorkflowBudget(), idempotency_key="orphan"
        )
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(investigation_workflows)) == 0


@pytest.mark.parametrize("kind", ["session", "api_key"])
def test_real_pg_actor_reference_reads_evidence_and_revocation_denies_reuse(
    workflow_resources, tmp_path, register_sensitive_failure_value, kind
):
    import time

    engine, _, _ = workflow_resources
    user_id, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    key_id = str(uuid4())
    if kind == "api_key":
        token = secrets.token_urlsafe(32)
        register_sensitive_failure_value(SecretStr(token))
        now = datetime.now(UTC)
        with engine.begin() as connection:
            connection.execute(
                api_keys.insert().values(
                    key_id=key_id,
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    user_id=user_id,
                    resource="urn:dianzi:api:v1",
                    scopes=["read:public"],
                    issued_at=now,
                    expires_at=now + timedelta(minutes=5),
                    version=1,
                )
            )
    credential = (
        ApiKeyCredential(SecretStr(token))
        if kind == "api_key"
        else SessionCredential(SecretStr(token))
    )
    with engine.begin() as connection:
        actor = create_actor_reference(connection, credential, datetime.now(UTC))
    call = (
        ReadEvidenceCall(
            tool_name="read_evidence", arguments=request.evidence_refs[0], goal_id=uuid4()
        )
        .model_dump_json()
        .encode()
    )
    with engine.connect() as connection:
        gateway = ToolGateway(
            Principal(user_id, "fixture-owner", Role.ANALYST),
            uuid4(),
            BudgetLimits(
                max_calls=2,
                max_concurrent_calls=1,
                max_request_bytes=4096,
                max_total_input_bytes=8192,
                max_result_bytes=16384,
                max_total_output_bytes=32768,
                deadline_monotonic=time.monotonic() + 15,
            ),
            evidence_reader=PostgresEvidenceReader(connection, actor, "fixture"),
        )
        first = gateway.execute(AgentRole.QA, call)
        assert first.status == "succeeded" and first.evidence_ids == (
            request.evidence_refs[0].evidence_id,
        )
        with engine.begin() as writer:
            if kind == "api_key":
                writer.execute(
                    update(api_keys)
                    .where(api_keys.c.key_id == key_id)
                    .values(revoked_at=datetime.now(UTC), version=2)
                )
            else:
                writer.execute(
                    update(auth_sessions)
                    .where(auth_sessions.c.user_id == user_id)
                    .values(revoked_at=datetime.now(UTC))
                )
        revoked = gateway.execute(AgentRole.QA, call)
        assert revoked.status == "denied" and revoked.data is None and revoked.evidence_ids == ()


@pytest.mark.parametrize(
    "change",
    [
        "asset_only",
        "principal_user",
        "principal_tenant",
        "principal_role",
        "scope_user",
        "scope_tenant",
        "scope_role",
        "scope_permission_version",
        "scope_missing_public",
        "scope_expands_private",
        "public_scope_private",
        "key_scope_revoked",
        "role_changed",
    ],
)
def test_real_pg_narrow_key_and_scope_cannot_expand_evidence_authority(
    workflow_resources, tmp_path, register_sensitive_failure_value, change
):
    import time

    engine, _, _ = workflow_resources
    user_id, _ = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(
        engine,
        tmp_path,
        scope=VisibilityScope(visibility="tenant", tenant_id="fixture-owner")
        if change in {"scope_expands_private", "public_scope_private"}
        else None,
    )
    token = secrets.token_urlsafe(32)
    register_sensitive_failure_value(SecretStr(token))
    key_id = str(uuid4())
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            api_keys.insert().values(
                key_id=key_id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user_id,
                resource="urn:dianzi:api:v1",
                scopes=["read:asset"] if change == "asset_only" else ["read:public"],
                issued_at=now,
                expires_at=now + timedelta(minutes=5),
                version=1,
            )
        )
        actor = create_actor_reference(connection, ApiKeyCredential(SecretStr(token)), now)
    principal = Principal(user_id, "fixture-owner", Role.ANALYST)
    scope = AccessScope.for_authenticated_user(user_id, "fixture-owner", Role.ANALYST)
    if change == "public_scope_private":
        scope = replace(scope, tenant_id=None)
    if change.startswith("principal_"):
        principal = replace(
            principal,
            **{
                "principal_user": {"user_id": str(uuid4())},
                "principal_tenant": {"tenant_id": "fixture-other"},
                "principal_role": {"role": Role.VIEWER},
            }[change],
        )
    elif change.startswith("scope_") and change != "scope_expands_private":
        scope = replace(
            scope,
            **{
                "scope_user": {"user_id": str(uuid4())},
                "scope_tenant": {"tenant_id": "fixture-other"},
                "scope_role": {"role": Role.VIEWER},
                "scope_permission_version": {"permission_version": 2},
                "scope_missing_public": {"permissions": frozenset({"read:asset"})},
            }[change],
        )
    elif change in {"key_scope_revoked", "role_changed"}:
        with engine.begin() as connection:
            if change == "role_changed":
                connection.execute(
                    update(users).where(users.c.user_id == user_id).values(role="viewer")
                )
            else:
                connection.execute(
                    update(api_keys)
                    .where(api_keys.c.key_id == key_id)
                    .values(scopes=["read:asset"], version=2)
                )
    with engine.connect() as connection:
        reader = PostgresEvidenceReader(connection, actor, "fixture")
        with pytest.raises((PermissionDeniedError, CrossTenantAccessError)):
            reader.read_evidence(principal, scope, request.evidence_refs[0], time.monotonic() + 15)


@pytest.mark.parametrize("strategy,model_calls", [("B2", 2), ("B2b", 2), ("B3", 3)])
def test_real_pg_supported_path_has_distinct_receipts_shared_evidence_and_no_replay_charge(
    workflow_resources,
    tmp_path,
    monkeypatch,
    register_sensitive_failure_value,
    strategy,
    model_calls,
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path, strategy=strategy)
    calls = []
    subject = service(workflow_resources, token, fixture_factory(monkeypatch, request, calls))
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="same-request")
    assert subject.enqueue(request, WorkflowBudget(), idempotency_key="same-request") == job_id
    context = claim(engine, job_id)
    result = subject.execute(context)
    assert result.status == "partial" and result.stop_reason == "adapter_gaps", [
        (receipt.role.value, receipt.reason_code) for receipt in result.receipts
    ]
    assert result.answer is not None and result.data_mode == "fixture"
    assert [receipt.role for receipt in result.receipts] == list(AgentRole)
    assert result.evidence_ids == (request.evidence_refs[0].evidence_id,)
    assert all(receipt.evidence_ids == result.evidence_ids for receipt in result.receipts[2:])
    assert len(calls) == model_calls
    replay = subject.execute(context)
    assert replay.answer == result.answer and len(calls) == model_calls
    with engine.connect() as connection:
        counters = connection.execute(
            select(
                func.sum(investigation_operations.c.model_calls),
                func.sum(investigation_operations.c.tool_calls),
            ).where(investigation_operations.c.job_id == str(job_id))
        ).one()
        assert counters == (model_calls, 2)
        assert (
            connection.scalar(select(job_runs.c.status).where(job_runs.c.job_id == str(job_id)))
            == "partial"
        )


def test_real_pg_candidate_injection_never_executes_tool(
    workflow_resources, tmp_path, monkeypatch, register_sensitive_failure_value
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path, strategy="B3")
    calls = []
    subject = service(
        workflow_resources,
        token,
        fixture_factory(monkeypatch, request, calls, planner_choice="shell:read_secret"),
    )
    result = subject.execute(
        claim(engine, subject.enqueue(request, WorkflowBudget(), idempotency_key="injection"))
    )
    assert result.status == "failed" and result.stop_reason == "planner_candidate_invalid"
    assert len(calls) == 1 and result.evidence_ids == () and result.answer is None
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(investigation_operations)
                .where(investigation_operations.c.kind == "tool")
            )
            == 0
        )


def test_real_pg_missing_model_and_empty_evidence_are_explicit_unknown(
    workflow_resources, tmp_path, register_sensitive_failure_value
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    subject = service(workflow_resources, token)
    result = subject.execute(
        claim(engine, subject.enqueue(request, WorkflowBudget(), idempotency_key="missing-model"))
    )
    assert result.answer is None and "generation_not_configured" in result.missing_requirements
    empty = request.model_copy(update={"evidence_refs": ()})
    result = subject.execute(
        claim(engine, subject.enqueue(empty, WorkflowBudget(), idempotency_key="empty"))
    )
    assert result.status == "partial" and result.answer is None and result.evidence_ids == ()
    assert "evidence_unavailable" in result.missing_requirements


def test_real_pg_budget_exhaustion_and_failed_critic_never_publish_answer(
    workflow_resources, tmp_path, monkeypatch, register_sensitive_failure_value
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    calls = []
    subject = service(
        workflow_resources, token, fixture_factory(monkeypatch, request, calls, unsupported=True)
    )
    result = subject.execute(
        claim(
            engine,
            subject.enqueue(request, WorkflowBudget(max_model_calls=1), idempotency_key="budget"),
        )
    )
    assert result.answer is None and len(calls) == 1
    result = subject.execute(
        claim(engine, subject.enqueue(request, WorkflowBudget(), idempotency_key="unsupported"))
    )
    assert (
        result.answer is None
        and "claim_support_missing" in result.missing_requirements
        and len(calls) == 3
    )


@pytest.mark.parametrize("tenant", ["fixture-owner", "fixture-other"])
def test_real_pg_same_tenant_non_owner_and_cross_tenant_cannot_load_result_or_checkpoint(
    workflow_resources, tmp_path, register_sensitive_failure_value, tenant
):
    engine, _, _ = workflow_resources
    _, owner_token = principal_session(engine, register_sensitive_failure_value)
    _, other_token = principal_session(engine, register_sensitive_failure_value, tenant)
    request = evidence_request(engine, tmp_path)
    owner_service = service(workflow_resources, owner_token)
    job_id = owner_service.enqueue(request, WorkflowBudget(), idempotency_key="owner")
    context = claim(engine, job_id)
    owner_service.execute(context, pause_after=("triage",))
    stranger = service(workflow_resources, other_token)
    with pytest.raises(CrossTenantAccessError):
        stranger.execute(context)
    with pytest.raises(CrossTenantAccessError):
        stranger.read_result(job_id)


@pytest.mark.parametrize("change", ["session", "role", "epoch"])
def test_real_pg_resume_rechecks_auth_role_and_epoch_before_checkpoint(
    workflow_resources, tmp_path, register_sensitive_failure_value, change
):
    engine, _, _ = workflow_resources
    user_id, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    subject = service(workflow_resources, token)
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key=change)
    context = claim(engine, job_id)
    subject.execute(context, pause_after=("triage",))
    with engine.begin() as connection:
        if change == "session":
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.user_id == user_id)
                .values(revoked_at=datetime.now(UTC))
            )
        elif change == "role":
            connection.execute(
                update(users).where(users.c.user_id == user_id).values(role="viewer")
            )
        else:
            connection.execute(
                update(scope_epochs)
                .where(scope_epochs.c.scope_key == "public")
                .values(epoch=scope_epochs.c.epoch + 1)
            )
    if change == "epoch":
        result = subject.execute(context)
        assert result.status == "stale" and result.answer is None and result.evidence_ids == ()
    else:
        with pytest.raises(
            (SessionExpiredError, CrossTenantAccessError, InvalidActorReferenceError)
        ):
            subject.execute(context)


def test_real_pg_current_auth_query_obeys_original_tool_deadline(
    workflow_resources, tmp_path, register_sensitive_failure_value
):
    import time

    engine, _, _ = workflow_resources
    user_id, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    injected = False

    def slow_auth_query(connection, cursor, statement, parameters, context, executemany):
        nonlocal injected
        if (
            not injected
            and statement.startswith("SELECT")
            and "FROM auth_sessions JOIN users" in statement
        ):
            injected = True
            return "SELECT pg_sleep(1)", ()
        return statement, parameters

    call = (
        ReadEvidenceCall(
            tool_name="read_evidence", arguments=request.evidence_refs[0], goal_id=uuid4()
        )
        .model_dump_json()
        .encode()
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
                deadline_monotonic=time.monotonic() + 0.15,
            ),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        event.listen(connection, "before_cursor_execute", slow_auth_query, retval=True)
        started = time.monotonic()
        try:
            result = gateway.execute(AgentRole.QA, call)
        finally:
            event.remove(connection, "before_cursor_execute", slow_auth_query)
        assert (
            injected
            and result.status == "budget_exhausted"
            and result.error_code == "deadline_exhausted"
        )
        assert time.monotonic() - started < 0.7 and result.data is None


def test_real_pg_asset_snapshot_change_stops_resume_without_old_assessment(
    workflow_resources, tmp_path, register_sensitive_failure_value
):
    engine, _, _ = workflow_resources
    user_id, token = principal_session(
        engine, register_sensitive_failure_value, role="tenant_admin"
    )
    request = evidence_request(engine, tmp_path)
    access = AccessScope.for_authenticated_user(user_id, "fixture-owner", Role.TENANT_ADMIN)

    def import_asset(version, asset_id=None):
        with Session(engine) as session, session.begin():
            return InventoryService(session, access).import_manifest(
                json.dumps(
                    {
                        "format_version": 1,
                        "components": [
                            {
                                "ecosystem": "pypi",
                                "package_name": "fixture-package",
                                "version": version,
                            }
                        ],
                    }
                ).encode(),
                manifest_format="json_manifest_v1",
                display_name="Synthetic workflow asset",
                source_version="synthetic-r14-1",
                observed_at=datetime.now(UTC),
                idempotency_key=uuid4().hex,
                asset_id=asset_id,
            )

    original = import_asset("1.0")
    request = request.model_copy(
        update={
            "asset_id": UUID(original.asset_id),
            "asset_snapshot_id": UUID(original.snapshot.snapshot_id),
        }
    )
    subject = service(workflow_resources, token)
    context = claim(engine, subject.enqueue(request, WorkflowBudget(), idempotency_key="asset"))
    subject.execute(context, pause_after=("triage",))
    import_asset("1.1", original.asset_id)
    result = subject.execute(context)
    assert result.status == "stale" and result.answer is None and result.evidence_ids == ()


def test_real_pg_execution_lock_rejects_concurrent_executor_before_saver(
    workflow_resources, tmp_path, register_sensitive_failure_value
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    subject = service(workflow_resources, token)
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="busy")
    context = claim(engine, job_id)
    lock_id = int.from_bytes(hashlib.sha256(str(job_id).encode()).digest()[:8], "big", signed=True)
    with engine.connect() as connection:
        connection.execute(select(func.pg_advisory_lock(lock_id)))
        connection.commit()
        with pytest.raises(WorkflowBusyError):
            subject.execute(context)
        connection.execute(select(func.pg_advisory_unlock(lock_id)))
        connection.commit()


def test_real_pg_success_receipt_and_owner_binding_are_immutable(
    workflow_resources, tmp_path, register_sensitive_failure_value
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    subject = service(workflow_resources, token)
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="immutable")
    subject.execute(claim(engine, job_id))
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(investigation_workflows)
            .where(investigation_workflows.c.job_id == str(job_id))
            .values(deadline_at=datetime.now(UTC) + timedelta(days=1))
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            update(investigation_operations)
            .where(
                investigation_operations.c.job_id == str(job_id),
                investigation_operations.c.status == "succeeded",
            )
            .values(output_json={"forged": True})
        )


def test_real_pg_unknown_reserved_model_is_spent_and_never_called_again(
    workflow_resources, tmp_path, monkeypatch, register_sensitive_failure_value
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    calls = []
    subject = service(workflow_resources, token, fixture_factory(monkeypatch, request, calls))
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="unknown-model")
    context = claim(engine, job_id)
    subject.execute(context, pause_after=("graph_writer",))
    with engine.begin() as connection:
        connection.execute(
            investigation_operations.insert().values(
                job_id=str(job_id),
                operation_key="model:qa",
                call_key="f" * 64,
                kind="model",
                role="qa",
                status="reserved",
                request_sha256="e" * 64,
                model_version="deepseek-flash",
                prompt_version="r14-qa-1",
                policy_version="r14-tool-gateway-1",
                pricing_version="unavailable",
                cost_status="unknown",
                input_bytes=65536,
                output_bytes=32768,
                model_calls=1,
                tool_calls=0,
                created_at=datetime.now(UTC),
            )
        )
    result = subject.execute(context)
    assert result.answer is None and calls == []
    assert "model_outcome_unknown" in result.missing_requirements
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.sum(investigation_operations.c.model_calls)).where(
                    investigation_operations.c.job_id == str(job_id)
                )
            )
            == 1
        )


@pytest.mark.parametrize("with_model", [False, True])
def test_real_pg_two_process_restart_recovers_same_input_hash_and_does_not_repeat_prior_tool(
    workflow_resources, tmp_path, register_sensitive_failure_value, with_model, monkeypatch
):
    engine, dsn, schema = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    subject = service(
        workflow_resources,
        token,
        fixture_factory(monkeypatch, request, []) if with_model else None,
    )
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="restart")
    context = claim(engine, job_id)
    test_file = Path(__file__).resolve()
    worker = """
import json, os, sys
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from ai_intel.investigation.workflow_service import InvestigationWorkflowService
from ai_intel.investigation.workflow_service import investigation_workflows
from ai_intel.api.actor_references import actor_reference_from_payload
from sqlalchemy import select
from ai_intel.workers.executor import JobExecutionContext
value=json.loads(sys.stdin.read())
engine=create_engine(value['url'],poolclass=NullPool,hide_parameters=True)
with engine.connect() as connection:
    stored=connection.scalar(select(investigation_workflows.c.actor_reference).where(
        investigation_workflows.c.job_id==value['job_id']))
calls=[]
factory=None
if value['with_model']:
    from pytest import MonkeyPatch
    from test_r14_langgraph_workflow_pg import fixture_factory
    from ai_intel.investigation.graph_contracts import InvestigationRequest
    factory=fixture_factory(MonkeyPatch(),InvestigationRequest.model_validate_json(json.dumps(value['request'])),calls)
subject=InvestigationWorkflowService(engine,actor_reference_from_payload(stored),
        value['dsn'],value['schema'],data_mode='fixture',model_factory=factory,
        model_provider='deepseek_openai' if factory else None,
        model_version='deepseek-flash' if factory else None)
context=JobExecutionContext(value['job_id'],'fixture-r14-worker',value['attempt'],value['tenant'])
pause='qa' if factory else 'triage'
result=subject.execute(context,pause_after=(pause,) if value['first'] else ())
print(json.dumps({'input_sha256':result.input_sha256,'status':result.status,
                  'evidence_ids':[str(item) for item in result.evidence_ids],
                  'model_calls':len(calls),'has_answer':result.answer is not None}))
engine.dispose()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        str(path)
        for path in (test_file.parents[2] / "src", test_file.parent, test_file.parents[1] / "unit")
    )
    payload = {
        "url": engine.url.render_as_string(hide_password=False),
        "dsn": dsn,
        "schema": schema,
        "job_id": str(job_id),
        "attempt": context.attempt_count,
        "tenant": context.tenant_id,
        "with_model": with_model,
        "request": request.model_dump(mode="json"),
    }
    snapshots = []
    for first in [True, False]:
        process = subprocess.run(
            [sys.executable, "-c", worker],
            input=json.dumps({**payload, "first": first}),
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert process.returncode == 0
        snapshots.append(json.loads(process.stdout))
    assert snapshots[0]["status"] == "running" and snapshots[1]["status"] == "partial"
    assert snapshots[0]["input_sha256"] == snapshots[1]["input_sha256"]
    assert [item["model_calls"] for item in snapshots] == ([1, 1] if with_model else [0, 0])
    assert snapshots[1]["has_answer"] == with_model
    assert (
        snapshots[0]["evidence_ids"]
        == snapshots[1]["evidence_ids"]
        == [str(request.evidence_refs[0].evidence_id)]
    )
    with engine.connect() as connection:
        assert connection.scalar(
            select(func.sum(investigation_operations.c.tool_calls)).where(
                investigation_operations.c.job_id == str(job_id)
            )
        ) == (2 if with_model else 1)
        assert connection.scalar(
            select(func.sum(investigation_operations.c.model_calls)).where(
                investigation_operations.c.job_id == str(job_id)
            )
        ) == (2 if with_model else 0)
