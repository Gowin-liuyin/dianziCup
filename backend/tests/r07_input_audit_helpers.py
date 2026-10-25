"""Owned PG schemas and explicitly offline codecs verify durable input audit behavior."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import CheckConstraint, create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.integration.test_r07_job_execution_pg import children, run, setup
from tests.unit.test_r07_single_model_dimension import prepared_transport

from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.models.generation import GenerationLimits

DATABASE = "test_dianzi_r07_input_audit_20261016"
SCHEMA_PREFIX = "test_r07_input_audit_"


def install_audit_proposal(engine: Engine) -> None:
    """Test-only forward proposal; the production 0023 migration remains root-owned."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE enrichment_job_steps ADD COLUMN IF NOT EXISTS "
                "input_audit_payload jsonb"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE enrichment_job_steps ADD COLUMN IF NOT EXISTS input_audit_sha256 text"
            )
        )
        from ai_intel.enrichment.job_models import (
            INPUT_AUDIT_IMMUTABILITY_DDL,
            enrichment_job_steps,
        )

        constraint = next(
            item
            for item in enrichment_job_steps.constraints
            if isinstance(item, CheckConstraint) and item.name == "ck_enrichment_step_input_audit"
        )
        connection.exec_driver_sql(
            "ALTER TABLE enrichment_job_steps ADD CONSTRAINT "
            + constraint.name
            + " CHECK ("
            + str(constraint.sqltext)
            + ")"
        )
        for statement in INPUT_AUDIT_IMMUTABILITY_DDL:
            connection.exec_driver_sql(statement)


def owned_audit_engine(
    isolated_test_database_url, register_sensitive_failure_value, *, install=True
) -> Iterator[Engine]:
    url = make_url(isolated_test_database_url)
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    register_sensitive_failure_value(SecretStr(url.password or ""))
    assert url.drivername == "postgresql+psycopg"
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, DATABASE)
    assert url.username and url.username.startswith("test_")
    assert os.environ["DIANZI_TEST_RUN_ID"] == "r07_input_audit_20261016"
    base = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    schema = SCHEMA_PREFIX + uuid4().hex
    with base.begin() as connection:
        count = connection.scalar(
            text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE :prefix"),
            {"prefix": SCHEMA_PREFIX + "%"},
        )
        assert count is not None and count < 80
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000"}
    )
    engine = create_engine(isolated, hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        run_migrations(
            isolated.render_as_string(hide_password=False),
            target_revision="0022_sbom_sidecars",
        )
        if install:
            install_audit_proposal(engine)
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


@pytest.fixture
def audit_engine(isolated_test_database_url, register_sensitive_failure_value) -> Iterator[Engine]:
    yield from owned_audit_engine(isolated_test_database_url, register_sensitive_failure_value)


@pytest.fixture
def legacy_audit_engine(
    isolated_test_database_url, register_sensitive_failure_value
) -> Iterator[Engine]:
    yield from owned_audit_engine(
        isolated_test_database_url, register_sensitive_failure_value, install=False
    )


@pytest.fixture
def default_api_audit_engine(
    isolated_test_database_url, register_sensitive_failure_value
) -> Iterator[Engine]:
    """Default factory replaces URL options; only this owned DB's default schema is redirected."""
    for engine in owned_audit_engine(isolated_test_database_url, register_sensitive_failure_value):
        with engine.connect() as connection:
            schema = connection.scalar(text("SELECT current_schema()"))
        assert (
            schema and schema.startswith(SCHEMA_PREFIX) and len(schema) == len(SCHEMA_PREFIX) + 32
        )
        base = create_engine(
            make_url(isolated_test_database_url), isolation_level="AUTOCOMMIT", hide_parameters=True
        )
        try:
            with base.connect() as connection:
                connection.exec_driver_sql(
                    'ALTER DATABASE "' + DATABASE + '" SET search_path TO "' + schema + '"'
                )
            yield engine
        finally:
            with base.connect() as connection:
                connection.exec_driver_sql('ALTER DATABASE "' + DATABASE + '" RESET search_path')
            base.dispose()


def prepared_workflow(engine: Engine, tmp_path, monkeypatch):
    policy = EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="openai",
        approved_model="fixture-model",
        data_mode="fixture",
    )
    service, scope, session_hash, event_id, request, receipt = setup(
        engine, tmp_path, policy=policy, source_kind="synthetic_bounded_paper"
    )
    calls = []

    def factory():
        client, wire = prepared_transport(
            monkeypatch,
            outputs={
                "versions": {"candidates": []},
                "literature": {"candidates": []},
                "poc": {"candidates": []},
                "atlas": {"candidates": []},
            },
        )
        client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
        calls.append(wire)
        return client

    service.generation_client_factory = factory
    assert run(service, receipt.parent_job_id) == "succeeded"
    step = next(item for item in children(service) if item["dimension"] == "versions")
    return service, scope, session_hash, event_id, request, receipt, step, calls
