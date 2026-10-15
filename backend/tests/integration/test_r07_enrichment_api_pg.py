"""Default API and worker wiring use real PG and explicitly synthetic source inputs."""

import importlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url
from test_r07_job_execution_pg import setup

from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import job_runs, users

pytestmark = pytest.mark.real_pg
ORIGIN = "http://127.0.0.1:25173"


@pytest.fixture
def execution_engine(isolated_test_database_url):
    """A dedicated public-schema database exercises the actual default engine factory."""
    url = make_url(isolated_test_database_url)
    assert url.database.startswith("test_dianzi_r07_execution_api_")
    database = "test_dianzi_r07_api_" + uuid4().hex
    administrator = create_engine(url, isolation_level="AUTOCOMMIT")
    with administrator.connect() as connection:
        connection.execute(text('CREATE DATABASE "' + database + '"'))
    administrator.dispose()
    isolated = url.set(database=database)
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated)
    try:
        yield engine
    finally:
        engine.dispose()


def application_client(engine, tmp_path, scope):
    settings = ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        database_url=SecretStr(engine.url.render_as_string(hide_password=False)),
        raw_content_directory=str(tmp_path),
        allowed_origins=(ORIGIN,),
    )
    client = TestClient(create_application(settings=settings))
    client.cookies.set(SESSION_COOKIE_NAME, "synthetic-r07-session:" + scope.user_id)
    return client


def test_default_api_queues_and_reads_workflow_without_model_or_content_io(
    execution_engine, tmp_path
):
    _, scope, _, event_id, _, original = setup(execution_engine, tmp_path)
    with application_client(execution_engine, tmp_path, scope) as client:
        initial = client.get("/v1/enrichment-workflows/" + str(original.workflow_id))
        assert initial.status_code == 200
        assert initial.json()["parent_status"] == "queued"
        assert initial.json()["workflow_complete"] is False
        headers = {
            "origin": ORIGIN,
            CSRF_HEADER_NAME: "synthetic-csrf",
            "Idempotency-Key": "api-case",
        }
        payload = {"expected_event_version": 1, "dimensions": ["cvss", "versions"]}
        first = client.post(f"/v1/events/{event_id}/enrichment-jobs", json=payload, headers=headers)
        assert first.status_code == 202
        repeated = client.post(
            f"/v1/events/{event_id}/enrichment-jobs", json=payload, headers=headers
        )
        assert repeated.status_code == 202 and repeated.json()["reused"] is True
        assert first.json()["workflow_id"] == repeated.json()["workflow_id"]
        job = client.get("/v1/jobs/" + first.json()["parent_job_id"])
        assert job.status_code == 200 and job.json()["status"] == "queued"
        assert "payload" not in job.json() and "actor_session_hash" not in job.json()
        view = client.get("/api/v1/enrichment-workflows/" + first.json()["workflow_id"])
        assert view.status_code == 200
        assert [item["dimension"] for item in view.json()["logical_dimensions"]] == [
            "cvss",
            "versions",
        ]
        assert "actor_session_hash" not in view.text and "synthetic-r07-session" not in view.text
        changed = client.post(
            f"/v1/events/{event_id}/enrichment-jobs",
            json={"expected_event_version": 1},
            headers=headers,
        )
        assert changed.status_code == 409
        assert client.get("/v1/jobs/" + str(uuid4())).status_code == 404
    with execution_engine.connect() as connection:
        assert len(connection.execute(select(enrichment_workflows)).all()) == 2


@pytest.mark.parametrize(
    "extra",
    [
        {"tenant_id": "forged"},
        {"generation_enabled": True},
        {"product_query_id": "arbitrary-query"},
    ],
)
def test_http_body_does_not_supply_identity_or_external_authority(
    execution_engine, tmp_path, extra
):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    with application_client(execution_engine, tmp_path, scope) as client:
        response = client.post(
            f"/v1/events/{event_id}/enrichment-jobs", json={"expected_event_version": 1, **extra}
        )
        assert response.status_code == 422


def test_missing_csrf_and_current_role_change_prevent_scheduling(execution_engine, tmp_path):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    with application_client(execution_engine, tmp_path, scope) as client:
        target = f"/v1/events/{event_id}/enrichment-jobs"
        assert client.post(target, json={"expected_event_version": 1}).status_code == 403
        with execution_engine.begin() as connection:
            connection.execute(
                update(users)
                .where(users.c.user_id == scope.user_id)
                .values(role="viewer", tenant_id="synthetic-changed-tenant")
            )
        response = client.post(
            target,
            json={"expected_event_version": 1},
            headers={
                "origin": ORIGIN,
                CSRF_HEADER_NAME: "synthetic-csrf",
                "Idempotency-Key": "denied",
            },
        )
        assert response.status_code == 403
        assert client.get("/v1/jobs/" + str(uuid4())).status_code == 403


def test_default_application_has_one_job_reader_and_unauthenticated_workflow_denial():
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture")
    )
    assert application.openapi()["paths"]["/v1/jobs/{job_id}"]["get"]["operationId"].startswith(
        "read_job_"
    )
    for prefix in ("/v1", "/api/v1"):
        with TestClient(application) as client:
            assert client.get(prefix + "/enrichment-workflows/" + str(uuid4())).status_code == 401


def worker_runtime(engine, tmp_path, monkeypatch):
    """Import the production task registry; only PG consumption runs, with no broker publish."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "fixture")
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/15")
    monkeypatch.setenv("CONTENT_STORE_BACKEND", "local")
    monkeypatch.setenv("RAW_CONTENT_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("ENRICHMENT_GENERATION_ENABLED", "false")
    monkeypatch.setenv("ENRICHMENT_AGGREGATE_ENABLED", "false")
    return importlib.import_module("ai_intel.workers.runtime")


@pytest.mark.parametrize(
    ("dimensions", "publication_status"),
    [(["cvss"], "succeeded"), (["cvss", "versions"], "partial")],
)
def test_default_api_to_registered_worker_publishes_atomic_structured_results(
    execution_engine, tmp_path, monkeypatch, dimensions, publication_status
):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    runtime = worker_runtime(execution_engine, tmp_path, monkeypatch)
    with application_client(execution_engine, tmp_path, scope) as client:
        response = client.post(
            f"/v1/events/{event_id}/enrichment-jobs",
            json={"expected_event_version": 1, "dimensions": dimensions},
            headers={
                "origin": ORIGIN,
                CSRF_HEADER_NAME: "synthetic-csrf",
                "Idempotency-Key": "registered-worker",
            },
        )
        assert response.status_code == 202
        workflow_id = response.json()["workflow_id"]
        parent_job_id = response.json()["parent_job_id"]
        assert runtime.consume_job(parent_job_id)["outcome"] == "succeeded"
        with execution_engine.connect() as connection:
            steps = (
                connection.execute(
                    select(enrichment_job_steps).where(
                        enrichment_job_steps.c.workflow_id == workflow_id
                    )
                )
                .mappings()
                .all()
            )
        assert len(steps) == len(dimensions) + 1
        for step in steps:
            if step["dimension"] is not None:
                outcome = runtime.consume_job(step["job_id"])["outcome"]
                with execution_engine.connect() as connection:
                    job_error = connection.scalar(
                        select(job_runs.c.error_code).where(job_runs.c.job_id == step["job_id"])
                    )
                if step["dimension"] == "versions":
                    assert outcome == "blocked" and job_error == "model_budget_not_authorized"
                else:
                    assert outcome == "succeeded", job_error
        with execution_engine.connect() as connection:
            assert not connection.execute(
                select(enrichment_results).where(
                    enrichment_results.c.publication_key.like("r07:" + workflow_id + "%")
                )
            ).all()
        publication = next(step for step in steps if step["step_key"] == "publication")
        assert runtime.consume_job(publication["job_id"])["outcome"] == publication_status
        complete = client.get("/v1/enrichment-workflows/" + workflow_id)
        assert complete.status_code == 200 and complete.json()["workflow_complete"] is True
        assert complete.json()["publication_status"] == publication_status
        assert runtime.consume_job(publication["job_id"])["outcome"] == "not_claimed"
        assert client.get("/v1/jobs/" + parent_job_id).json()["status"] == "succeeded"
    with execution_engine.connect() as connection:
        results = (
            connection.execute(
                select(enrichment_results.c.dimension).where(
                    enrichment_results.c.publication_key.like("r07:" + workflow_id + "%")
                )
            )
            .scalars()
            .all()
        )
        assert sorted(results) == dimensions


def test_registered_worker_rechecks_changed_actor_role_before_creating_children(
    execution_engine, tmp_path, monkeypatch
):
    _, scope, _, _, _, receipt = setup(execution_engine, tmp_path)
    with execution_engine.connect() as connection:
        before_results = connection.execute(select(enrichment_results.c.result_id)).scalars().all()
    runtime = worker_runtime(execution_engine, tmp_path, monkeypatch)
    with execution_engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == scope.user_id)
            .values(role="viewer", tenant_id="synthetic-changed-tenant")
        )
    assert runtime.consume_job(str(receipt.parent_job_id))["outcome"] == "blocked"
    with execution_engine.connect() as connection:
        assert not connection.execute(select(enrichment_job_steps)).all()
        assert (
            connection.execute(select(enrichment_results.c.result_id)).scalars().all()
            == before_results
        )
