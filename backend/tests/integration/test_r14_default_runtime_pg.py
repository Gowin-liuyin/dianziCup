"""Real marked PG and checkpoints; source/model inputs are explicit synthetic fixtures."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_r14_langgraph_workflow_pg import (
    evidence_request,
    fixture_factory,
    principal_session,
    service,
)
from test_r14_langgraph_workflow_pg import (
    workflow_resources as workflow_resources,
)

from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore, auth_sessions
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.investigation_routes import build_investigation_router
from ai_intel.domain.enums import ToolStatus
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.investigation.graph_contracts import WorkflowBudget
from ai_intel.investigation.tool_gateway import ToolGateway
from ai_intel.investigation.workflow_service import (
    InvestigationWorkflowService,
    investigation_operations,
)
from ai_intel.knowledge.models import job_runs, job_transitions, users
from ai_intel.workers.investigation import execute_investigation_job
from ai_intel.workers.jobs import recover_expired_job_deliveries

pytestmark = pytest.mark.real_pg


def factory_for(resources, model=None):
    engine, dsn, schema = resources
    return lambda actor: InvestigationWorkflowService(
        engine,
        actor,
        dsn,
        schema,
        data_mode="fixture",
        model_factory=model,
        model_provider="deepseek_openai" if model else None,
        model_version="deepseek-flash" if model else None,
    )


def api_client(resources):
    engine, _, schema = resources
    authentication = AuthenticationSessionService(
        DatabaseUserDirectory(engine),
        ("http://testserver",),
        False,
        state_store=PgAuthenticationStateStore(engine),
    )
    application = FastAPI()
    application.include_router(
        build_investigation_router(
            lambda: authentication,
            engine,
            ApplicationSettings(app_env="test", data_mode="fixture"),
            checkpoint_schema=schema,
        ),
        prefix="/v1",
    )
    return TestClient(application)


def request_headers():
    return {
        "Origin": "http://testserver",
        CSRF_HEADER_NAME: "fixture-unused",
        "Idempotency-Key": "synthetic-r14-create",
    }


def test_driver_real_terminal_is_owned_by_workflow_and_replay_has_no_charge(
    workflow_resources,
    tmp_path,
    monkeypatch,
    register_sensitive_failure_value,
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    calls = []
    model = fixture_factory(monkeypatch, request, calls)
    subject = service(workflow_resources, token, model)
    job = subject.enqueue(request, WorkflowBudget(), idempotency_key="driver-terminal")
    driver_factory = factory_for(workflow_resources, model)
    assert (
        execute_investigation_job(engine, str(job), "synthetic-worker-one", driver_factory)
        == "partial"
    )
    assert len(calls) == 2
    assert (
        execute_investigation_job(engine, str(job), "synthetic-worker-two", driver_factory)
        == "not_claimed"
    )
    assert len(calls) == 2
    result = subject.read_result(job)
    assert result.answer is not None and result.stop_reason == "adapter_gaps"
    with engine.connect() as connection:
        terminal = (
            connection.execute(
                select(job_transitions.c.to_status).where(job_transitions.c.job_id == str(job))
            )
            .scalars()
            .all()
        )
        assert terminal == ["running", "partial"]
        assert (
            connection.scalar(select(job_runs.c.attempt_count).where(job_runs.c.job_id == str(job)))
            == 1
        )


def test_driver_does_not_claim_other_job_types(workflow_resources):
    engine, _, _ = workflow_resources
    with Session(engine) as session, session.begin():
        job = enqueue_job(session, None, "record_source_fetch_failure", b"{}", datetime.now(UTC))

    def never_factory(actor):
        raise AssertionError("unrelated job reached investigation")

    assert (
        execute_investigation_job(engine, job, "synthetic-wrong-type", never_factory)
        == "not_claimed"
    )
    with engine.connect() as connection:
        assert connection.execute(
            select(job_runs.c.status, job_runs.c.attempt_count).where(job_runs.c.job_id == job)
        ).one() == ("queued", 0)


@pytest.mark.parametrize("change", ["revoked", "role_changed"])
def test_driver_rechecks_stored_actor_before_external_io(
    workflow_resources,
    tmp_path,
    register_sensitive_failure_value,
    change,
):
    engine, _, _ = workflow_resources
    owner, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    job = service(workflow_resources, token).enqueue(
        request, WorkflowBudget(), idempotency_key="driver-actor"
    )
    with engine.begin() as connection:
        if change == "revoked":
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.user_id == owner)
                .values(revoked_at=datetime.now(UTC))
            )
        else:
            connection.execute(update(users).where(users.c.user_id == owner).values(role="viewer"))
    assert (
        execute_investigation_job(
            engine, str(job), "synthetic-actor", factory_for(workflow_resources)
        )
        == "blocked"
    )
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(investigation_operations)
                .where(investigation_operations.c.job_id == str(job))
            )
            == 0
        )


def test_driver_waiting_approval_is_not_completed_again(
    workflow_resources,
    tmp_path,
    monkeypatch,
    register_sensitive_failure_value,
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    job = service(workflow_resources, token).enqueue(
        request, WorkflowBudget(), idempotency_key="driver-wait"
    )
    original = ToolGateway.execute

    def synthetic_permission_denial(gateway, role, raw):
        actual = original(gateway, role, raw)
        return actual.model_copy(
            update={
                "status": ToolStatus.DENIED,
                "data": None,
                "evidence_ids": (),
                "error_code": "permission_required",
            }
        )

    monkeypatch.setattr(ToolGateway, "execute", synthetic_permission_denial)
    assert (
        execute_investigation_job(
            engine, str(job), "synthetic-approval", factory_for(workflow_resources)
        )
        == "waiting_approval"
    )
    assert (
        execute_investigation_job(
            engine, str(job), "synthetic-approval-repeat", factory_for(workflow_resources)
        )
        == "not_claimed"
    )
    with engine.connect() as connection:
        assert connection.execute(
            select(job_runs.c.status, job_runs.c.lease_owner, job_runs.c.error_code).where(
                job_runs.c.job_id == str(job)
            )
        ).one() == ("waiting_approval", None, "permission_required")


def test_driver_concurrent_duplicate_delivery_has_single_claim(
    workflow_resources,
    tmp_path,
    register_sensitive_failure_value,
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    job = service(workflow_resources, token).enqueue(
        request, WorkflowBudget(), idempotency_key="driver-concurrent"
    )
    driver_factory = factory_for(workflow_resources)
    entered = Event()
    continue_graph = Event()

    def paused_factory(actor):
        entered.set()
        assert continue_graph.wait(10)
        return driver_factory(actor)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            execute_investigation_job, engine, str(job), "synthetic-concurrent-a", paused_factory
        )
        assert entered.wait(10)
        duplicate = executor.submit(
            execute_investigation_job, engine, str(job), "synthetic-concurrent-b", driver_factory
        )
        assert duplicate.result(timeout=10) == "not_claimed"
        continue_graph.set()
        outputs = [first.result(timeout=30), "not_claimed"]
    assert sorted(outputs) == ["not_claimed", "partial"]
    with engine.connect() as connection:
        assert (
            connection.scalar(select(job_runs.c.attempt_count).where(job_runs.c.job_id == str(job)))
            == 1
        )


def test_driver_process_loss_and_redelivery_resume_without_repeating_confirmed_qa(
    workflow_resources,
    tmp_path,
    monkeypatch,
    register_sensitive_failure_value,
):
    engine, dsn, schema = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    job = service(workflow_resources, token, fixture_factory(monkeypatch, request, [])).enqueue(
        request, WorkflowBudget(), idempotency_key="driver-process-loss"
    )
    worker = """
import json,sys,os
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from pytest import MonkeyPatch
from test_r14_langgraph_workflow_pg import fixture_factory
from ai_intel.investigation.graph_contracts import InvestigationRequest
from ai_intel.investigation.workflow_service import InvestigationWorkflowService
from ai_intel.workers.investigation import execute_investigation_job
v=json.loads(sys.stdin.read()); e=create_engine(v['url'],poolclass=NullPool,hide_parameters=True)
c=[]
request=InvestigationRequest.model_validate_json(json.dumps(v['request']))
m=fixture_factory(MonkeyPatch(),request,c)
def f(a):
 return InvestigationWorkflowService(e,a,v['dsn'],v['schema'],data_mode='fixture',
  model_factory=m,model_provider='deepseek_openai',model_version='deepseek-flash')
r=execute_investigation_job(e,v['job'],'synthetic-process-'+str(v['first']),f,
 pause_after=('qa',) if v['first'] else ())
if v['first']:
 os._exit(73)
print(json.dumps({'status':r,'calls':len(c)}));e.dispose()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(Path(__file__).parents[2] / "src"),
            str(Path(__file__).parent),
            str(Path(__file__).parents[1] / "unit"),
        ]
    )
    envelope = dict(
        url=engine.url.render_as_string(hide_password=False),
        dsn=dsn,
        schema=schema,
        job=str(job),
        request=request.model_dump(mode="json"),
    )
    first = subprocess.run(
        [sys.executable, "-c", worker],
        input=json.dumps({**envelope, "first": True}),
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert first.returncode == 73
    with engine.begin() as connection:
        assert (
            connection.scalar(select(job_runs.c.status).where(job_runs.c.job_id == str(job)))
            == "running"
        )
        assert (
            connection.scalar(
                select(investigation_operations.c.status).where(
                    investigation_operations.c.job_id == str(job),
                    investigation_operations.c.operation_key == "model:qa",
                )
            )
            == "succeeded"
        )
        connection.execute(
            update(job_runs)
            .where(job_runs.c.job_id == str(job))
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    with Session(engine) as session, session.begin():
        assert recover_expired_job_deliveries(session, datetime.now(UTC)) in {0, 1}
    second = subprocess.run(
        [sys.executable, "-c", worker],
        input=json.dumps({**envelope, "first": False}),
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout) == {"status": "partial", "calls": 1}
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.sum(investigation_operations.c.model_calls)).where(
                    investigation_operations.c.job_id == str(job)
                )
            )
            == 2
        )
        assert (
            connection.scalar(select(job_runs.c.attempt_count).where(job_runs.c.job_id == str(job)))
            == 2
        )


def test_http_real_enqueue_read_receipts_and_idempotency_conflict(
    workflow_resources,
    tmp_path,
    register_sensitive_failure_value,
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    with api_client(workflow_resources) as client:
        client.cookies.set(SESSION_COOKIE_NAME, token)
        first = client.post(
            "/v1/investigations", json=request.model_dump(mode="json"), headers=request_headers()
        )
        assert first.status_code == 202, first.text
        body = first.json()
        job = body["job_id"]
        assert body["status"] == "queued" and body["result"] is None
        assert (
            client.post(
                "/v1/investigations",
                json=request.model_dump(mode="json"),
                headers=request_headers(),
            ).json()["job_id"]
            == job
        )
        changed = request.model_copy(update={"question": "不同合成问题"})
        assert (
            client.post(
                "/v1/investigations",
                json=changed.model_dump(mode="json"),
                headers=request_headers(),
            ).status_code
            == 409
        )
        assert (
            execute_investigation_job(
                engine, job, "synthetic-http", factory_for(workflow_resources)
            )
            == "partial"
        )
        read = client.get("/v1/investigations/" + job)
        assert read.status_code == 200 and read.json()["status"] == "partial"
        assert read.json()["result"]["answer"] is None
        assert read.json()["elapsed_milliseconds"] > 0
        page = client.get("/v1/investigations/" + job + "/tool-runs", params={"limit": 1})
        assert page.status_code == 200 and len(page.json()["items"]) == 1
        assert page.json()["next_cursor"] is not None
        assert set(page.json()["items"][0]).isdisjoint(
            {"output_json", "actor_reference", "input_json", "session_hash", "token"}
        )
        assert token not in read.text and token not in page.text


@pytest.mark.parametrize("tenant", ["fixture-owner", "fixture-other"])
def test_http_non_owner_cannot_read_or_cancel_job_or_receipts(
    workflow_resources,
    tmp_path,
    register_sensitive_failure_value,
    tenant,
):
    engine, _, _ = workflow_resources
    _, owner_token = principal_session(engine, register_sensitive_failure_value)
    _, other_token = principal_session(
        engine, register_sensitive_failure_value, tenant=tenant, role="tenant_admin"
    )
    request = evidence_request(engine, tmp_path)
    job = service(workflow_resources, owner_token).enqueue(
        request, WorkflowBudget(), idempotency_key="http-owner"
    )
    with api_client(workflow_resources) as client:
        client.cookies.set(SESSION_COOKIE_NAME, other_token)
        for suffix in ["", "/tool-runs"]:
            assert client.get("/v1/investigations/" + str(job) + suffix).status_code == 404
        assert (
            client.post(
                "/v1/investigations/" + str(job) + "/cancel", headers=request_headers()
            ).status_code
            == 404
        )


@pytest.mark.parametrize("role,status", [("analyst", 403), ("tenant_admin", 200)])
def test_http_cancel_preserves_existing_write_permission_and_stops_delivery(
    workflow_resources,
    tmp_path,
    register_sensitive_failure_value,
    role,
    status,
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value, role=role)
    request = evidence_request(engine, tmp_path)
    job = service(workflow_resources, token).enqueue(
        request, WorkflowBudget(), idempotency_key="http-cancel"
    )
    with api_client(workflow_resources) as client:
        client.cookies.set(SESSION_COOKIE_NAME, token)
        result = client.post(
            "/v1/investigations/" + str(job) + "/cancel", headers=request_headers()
        )
        assert result.status_code == status, result.text
        if status == 200:
            assert result.json()["status"] == "cancelled"
            assert (
                client.post(
                    "/v1/investigations/" + str(job) + "/cancel", headers=request_headers()
                ).status_code
                == 200
            )
            assert (
                execute_investigation_job(
                    engine, str(job), "synthetic-cancel", factory_for(workflow_resources)
                )
                == "not_claimed"
            )


def test_http_csrf_bearer_and_revocation_are_not_success(
    workflow_resources,
    tmp_path,
    register_sensitive_failure_value,
):
    engine, _, _ = workflow_resources
    owner, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    job = service(workflow_resources, token).enqueue(
        request, WorkflowBudget(), idempotency_key="http-auth"
    )
    with api_client(workflow_resources) as client:
        client.cookies.set(SESSION_COOKIE_NAME, token)
        assert (
            client.post(
                "/v1/investigations",
                json=request.model_dump(mode="json"),
                headers={"Idempotency-Key": "bad-csrf"},
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/v1/investigations/" + str(job),
                headers={"Authorization": "Bearer synthetic-read-key"},
            ).status_code
            == 401
        )
        with engine.begin() as connection:
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.user_id == owner)
                .values(revoked_at=datetime.now(UTC))
            )
        assert client.get("/v1/investigations/" + str(job)).status_code == 401
