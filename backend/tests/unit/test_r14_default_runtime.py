"""Isolated factory, transport and strict-input checks do not connect services or models."""

from uuid import uuid4

import pytest
from celery import Celery
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.credentials import SessionCredential
from ai_intel.api.investigation_routes import build_investigation_router
from ai_intel.infrastructure.models.generation import GenerationLimits
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.investigation.graph_contracts import InvestigationRequest, WorkflowBudget
from ai_intel.investigation.runtime import build_investigation_service
from ai_intel.workers.investigation import (
    INVESTIGATION_HARD_LIMIT_SECONDS,
    INVESTIGATION_QUEUE,
    INVESTIGATION_SOFT_LIMIT_SECONDS,
    INVESTIGATION_TASK,
    INVESTIGATION_VISIBILITY_TIMEOUT_SECONDS,
    build_investigation_celery_application,
    configure_investigation_task,
    investigation_task_for_event,
)


def test_dedicated_task_keeps_ordinary_limits_and_has_frozen_long_budget():
    application = Celery("synthetic-r14-config", broker="memory://", backend=None)
    application.conf.update(task_soft_time_limit=25, task_time_limit=30)
    configure_investigation_task(application)
    task = application.tasks[INVESTIGATION_TASK]
    assert task.soft_time_limit == 610 and task.time_limit == 620
    assert task.acks_late is True and task.reject_on_worker_lost is True
    assert task.autoretry_for == ()
    assert application.conf.task_soft_time_limit == 25
    assert application.conf.task_time_limit == 30
    assert application.conf.task_routes[INVESTIGATION_TASK] == {"queue": INVESTIGATION_QUEUE}
    assert (
        WorkflowBudget(total_seconds=600.0).total_seconds
        < INVESTIGATION_SOFT_LIMIT_SECONDS
        < INVESTIGATION_HARD_LIMIT_SECONDS
        < INVESTIGATION_VISIBILITY_TIMEOUT_SECONDS
    )
    with pytest.raises(ValidationError):
        WorkflowBudget(total_seconds=600.01)


def test_dedicated_application_does_not_connect_and_bounds_broker_visibility():
    application = build_investigation_celery_application(
        ApplicationSettings(
            app_env="test",
            data_mode="fixture",
            database_url=SecretStr("postgresql://test_fixture@127.0.0.1/test_dianzi_factory"),
            redis_url=SecretStr("redis://127.0.0.1:26379/15"),
        )
    )
    assert application.conf.task_default_queue == INVESTIGATION_QUEUE
    assert application.conf.worker_concurrency == 1
    assert application.conf.broker_transport_options["visibility_timeout"] == 660
    assert application.backend.__class__.__name__ == "DisabledBackend"


@pytest.mark.parametrize(
    "topic", ["job.collect_source_page", "job.knowledge_change", "", "job.shell"]
)
def test_unrelated_outbox_topics_are_not_routed_to_investigation(topic):
    assert investigation_task_for_event({"topic": topic}) is None
    assert investigation_task_for_event({"topic": "job.investigation"}) == INVESTIGATION_TASK


@pytest.mark.parametrize("configured", [False, True])
def test_runtime_uses_frozen_config_and_does_not_call_model(configured):
    engine = create_engine("postgresql+psycopg://test_fixture@127.0.0.1/test_dianzi_factory")
    settings = ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        dns_resolver="cloudflare_doh",
        generation_api_key=SecretStr("synthetic-r14-runtime-credential") if configured else None,
    )
    subject = build_investigation_service(
        engine, settings, SessionCredential(SecretStr("synthetic-session"))
    )
    assert subject.data_mode == "fixture"
    assert subject._checkpoint_schema == "dianzi_investigation_checkpoints"
    if configured:
        assert subject.model_factory is not None
        client = subject.model_factory(GenerationLimits(max_calls=1))
        assert client.provider == "deepseek_openai" and client.approved_model == "deepseek-flash"
        assert client._gateway._policy.dns_resolver == "cloudflare_doh"
    else:
        assert subject.model_factory is None
    engine.dispose()


@pytest.mark.parametrize(
    "extra", ["tenant_id", "role", "budget", "thread_id", "checkpoint_schema", "actor_reference"]
)
def test_route_contract_rejects_client_authority(extra):
    application = FastAPI()
    application.include_router(
        build_investigation_router(
            lambda: None, None, ApplicationSettings(app_env="test", data_mode="fixture")
        )
    )
    with TestClient(application) as client:
        response = client.post(
            "/investigations",
            json={
                "question": "合成问题",
                "event_id": str(uuid4()),
                "evidence_refs": [],
                extra: "synthetic",
            },
        )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "path", ["/investigations/" + str(uuid4()), "/investigations/" + str(uuid4()) + "/tool-runs"]
)
def test_router_denies_uncredentialed_reads_without_touching_pg(path):
    application = FastAPI()
    application.include_router(
        build_investigation_router(
            lambda: None, None, ApplicationSettings(app_env="test", data_mode="fixture")
        )
    )
    with TestClient(application) as client:
        response = client.get(path)
    assert response.status_code == 401 and "session_expired" in response.text


def test_create_without_database_is_explicit_unavailable_not_success():
    application = FastAPI()
    application.include_router(
        build_investigation_router(
            lambda: None, None, ApplicationSettings(app_env="test", data_mode="fixture")
        )
    )
    with TestClient(application) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "synthetic-session")
        response = client.post(
            "/investigations",
            json=InvestigationRequest(
                question="合成问题", event_id=uuid4(), evidence_refs=()
            ).model_dump(mode="json"),
            headers={"Idempotency-Key": "synthetic-create"},
        )
    assert response.status_code == 503


@pytest.mark.parametrize("kind", ["duplicate_key", "oversized"])
def test_transport_rejects_ambiguous_or_oversized_json_before_pg(kind):
    application = FastAPI()
    application.include_router(
        build_investigation_router(
            lambda: None, None, ApplicationSettings(app_env="test", data_mode="fixture")
        )
    )
    raw = (
        b'{"question":"first","question":"second"}'
        if kind == "duplicate_key"
        else b'{"question":"' + b"x" * 65536 + b'"}'
    )
    with TestClient(application) as client:
        response = client.post(
            "/investigations", content=raw, headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 422
    assert "first" not in response.text and "second" not in response.text
