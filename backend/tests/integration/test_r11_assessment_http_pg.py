"""Synthetic evidence in an owned real-PG schema; no live provider or production resource."""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import MetaData, Table, create_engine, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from tests.integration import test_r11_pg_assessments as original

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME, build_auth_router
from ai_intel.api.auth_state import PgAuthenticationStateStore, auth_sessions
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.http_contracts import AssessmentResponse
from ai_intel.assessment.http_routes import build_assessment_router
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assets.inventory import InventoryService
from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import document_revisions, users

pytestmark = pytest.mark.real_pg
RUN_ID = "r11_assessment_http_20261016"
DATABASE = "test_dianzi_" + RUN_ID
SCHEMA_PREFIX = "test_r11_assessment_http_"
ORIGIN = "http://testserver"
HEAD = "0031_public_task_bindings"


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, DATABASE)
    assert url.username and url.username.startswith("test_") and url.password
    schema = SCHEMA_PREFIX + uuid4().hex
    base = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with base.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == DATABASE
        assert str(connection.scalar(text("SELECT current_user"))).startswith("test_")
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(
            f'CREATE TABLE "{schema}".assessment_http_test_marker '
            "(run_id TEXT PRIMARY KEY, synthetic BOOLEAN NOT NULL CHECK(synthetic), "
            "created_at TIMESTAMPTZ NOT NULL)"
        )
        connection.execute(
            text(f'INSERT INTO "{schema}".assessment_http_test_marker VALUES (:run, true, :time)'),
            dict(run=RUN_ID, time=datetime.now(UTC)),
        )
    base.dispose()
    migration_url = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    runtime_url = url.update_query_dict(
        {
            "options": f"-c search_path={schema},public "
            "-c statement_timeout=15000 -c lock_timeout=5000"
        }
    )
    real_create_engine, real_table_create = sqlalchemy.create_engine, Table.create

    def migration_engine(*arguments, **keywords):
        return real_create_engine(*arguments, **keywords, poolclass=NullPool, hide_parameters=True)

    def forbid_metadata(*arguments, **keywords):
        raise AssertionError("only production forward migrations may create business tables")

    def only_alembic_table(table, *arguments, **keywords):
        assert table.name == "alembic_version"
        return real_table_create(table, *arguments, **keywords)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sqlalchemy, "create_engine", migration_engine)
        patch.setattr(MetaData, "create_all", forbid_metadata)
        patch.setattr(Table, "create", only_alembic_table)
        run_migrations(migration_url.render_as_string(hide_password=False))
    engine = create_engine(runtime_url, poolclass=NullPool, hide_parameters=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        assert connection.scalar(text("SELECT run_id FROM assessment_http_test_marker")) == RUN_ID
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    evidence = os.environ.get("R11_ASSESSMENT_HTTP_EVIDENCE_DIR")
    if evidence:
        Path(evidence, "pg_schema_receipt.json").write_text(
            json.dumps(
                dict(
                    schema=schema,
                    database=DATABASE,
                    revision=HEAD,
                    forward_only=True,
                    retained=True,
                    pool="NullPool",
                    maximum_connections=2,
                    synthetic=True,
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def sensitive_failure_guard(register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(make_url(os.environ["TEST_DATABASE_URL"]).password))


def authentication(engine):
    return AuthenticationSessionService(
        DatabaseUserDirectory(engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(engine),
    )


@contextmanager
def client_for(engine, store, token=None):
    app = FastAPI()

    def provider():
        return authentication(engine)

    app.include_router(
        build_auth_router(provider, ApplicationSettings(app_env="test", data_mode="fixture")),
        prefix="/v1",
    )
    app.include_router(build_assessment_router(provider, engine, store), prefix="/v1")
    with TestClient(app) as client:
        if token is not None:
            client.cookies.set(SESSION_COOKIE_NAME, token)
            record = authentication(engine).session_record(token)
            client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": record.csrf_token})
        yield client


def case(engine, directory, *, published=True, public=False):
    seeded = original.seed(engine, directory, public=public)
    if published:
        original.publish(engine, seeded)
    imported = original.asset(engine, seeded)
    payload = dict(
        asset_id=imported.asset_id,
        asset_snapshot_id=imported.snapshot.snapshot_id,
        rule_id=seeded["rule"].rule_id,
        rule_version=1,
    )
    return seeded, imported, payload


def assert_problem(response, status, code):
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Content-Type"] == "application/problem+json"
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["details"] == {}


def saved_payload(engine, identity):
    with engine.connect() as connection:
        return connection.scalar(
            select(assessment_results.c.result_payload).where(
                assessment_results.c.assessment_id == identity
            )
        )


def test_real_login_analyst_prepare_commit_read_rebuild_and_input_idempotency(pg_engine, tmp_path):
    seeded, _, payload = case(pg_engine, tmp_path)
    auth = authentication(pg_engine)
    password = SecretStr("synthetic-assessment-http-" + uuid4().hex)
    username = "fixture-http-" + uuid4().hex
    auth.create_precreated_user(
        username, password.get_secret_value(), seeded["tenant"], Role.ANALYST
    )
    with client_for(pg_engine, seeded["store"]) as client:
        login = client.post(
            "/v1/auth/login",
            json=dict(username=username, password=password.get_secret_value()),
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        token = client.cookies.get(SESSION_COOKIE_NAME)
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]})
        posted = client.post("/v1/assessments", json=payload)
        assert posted.status_code == 200
        result = posted.json()
        assert result["status"] == "supported_applicability" and result["freshness"] == "current"
        assert not result["reused"] and "prepared" not in result
        assert posted.headers["Cache-Control"] == "no-store"
        identity = result["assessment_id"]
        original_payload = saved_payload(pg_engine, identity)
        assert "prepared" in original_payload
        assert result == AssessmentResponse.from_receipt(
            AssessmentReceipt.model_validate(original_payload)
        ).model_dump(mode="json")
        assert result["rule_result"]["evaluation_tree"]["evidence_ids"] == [seeded["evidence_id"]]
        assert result["rule_result"]["evaluation_tree"]["asset_field_refs"]
    with client_for(pg_engine, seeded["store"], token) as rebuilt:
        read = rebuilt.get("/v1/assessments/" + identity)
        assert read.status_code == 200 and read.json() == result
        replay = rebuilt.post("/v1/assessments", json=payload)
        assert replay.status_code == 200 and replay.json()["assessment_id"] == identity
        assert replay.json()["reused"]
        assert saved_payload(pg_engine, identity) == original_payload
    evidence = os.environ.get("R11_ASSESSMENT_HTTP_EVIDENCE_DIR")
    if evidence:
        Path(evidence, "serialized_receipt_example.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )


@pytest.mark.parametrize(
    "version,expected,value",
    [
        ("1.4.1", "supported_applicability", "true"),
        ("1.4.2", "excluded_with_evidence", "false"),
        (None, "insufficient_evidence", "unknown"),
        ("conflict", "conflicting_evidence", "conflict"),
    ],
)
def test_http_four_states_remain_service_truth(pg_engine, tmp_path, version, expected, value):
    seeded = original.seed(pg_engine, tmp_path)
    original.publish(pg_engine, seeded)
    if version == "conflict":
        raw = json.dumps(
            dict(
                format_version=1,
                components=[
                    dict(ecosystem="PyPI", package_name="fixture", version="1.4.1"),
                    dict(ecosystem="PyPI", package_name="fixture", version="1.4.2"),
                ],
            )
        ).encode()
        with Session(pg_engine) as session, session.begin():
            imported = InventoryService(session, seeded["asset_actor"]).import_manifest(
                raw,
                manifest_format="json_manifest_v1",
                display_name="Synthetic HTTP conflict asset",
                source_version="fixture-1",
                observed_at=original.STAMP,
                idempotency_key=uuid4().hex,
            )
    else:
        imported = original.asset(pg_engine, seeded, version)
    payload = dict(
        asset_id=imported.asset_id,
        asset_snapshot_id=imported.snapshot.snapshot_id,
        rule_id=seeded["rule"].rule_id,
        rule_version=1,
    )
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as client:
        response = client.post("/v1/assessments", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert (
            result["status"] == expected
            and result["rule_result"]["evaluation_tree"]["value"] == value
        )
        assert (
            result["freshness"] == "current" and result["exploit_evidence_status"] == "not_verified"
        )
        if value == "unknown":
            assert result["missing_requirements"]
        if value == "conflict":
            assert len(result["conflicts"]) == 2


def test_unpublished_rule_is_insufficient_and_missing_rule_uniform_404(pg_engine, tmp_path):
    seeded, _, payload = case(pg_engine, tmp_path, published=False)
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as client:
        response = client.post("/v1/assessments", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "insufficient_evidence"
        assert response.json()["rule_result"] is None
        assert response.json()["missing_requirements"] == ["unsupported_rule"]
        assert_problem(
            client.post("/v1/assessments", json=dict(payload, rule_id=str(uuid4()))),
            404,
            "not_found",
        )


def test_history_retains_original_status_and_storage_after_new_snapshot(pg_engine, tmp_path):
    seeded, imported, payload = case(pg_engine, tmp_path)
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as client:
        first = client.post("/v1/assessments", json=payload).json()
        before = saved_payload(pg_engine, first["assessment_id"])
        newer = original.asset(pg_engine, seeded, "1.4.2", asset_id=imported.asset_id)
        read = client.get("/v1/assessments/" + first["assessment_id"])
        assert read.status_code == 200
        assert (
            read.json()["status"] == "supported_applicability"
            and read.json()["freshness"] == "stale"
        )
        new_result = client.post(
            "/v1/assessments", json=dict(payload, asset_snapshot_id=newer.snapshot.snapshot_id)
        )
        assert new_result.status_code == 200
        assert (
            new_result.json()["status"] == "excluded_with_evidence"
            and new_result.json()["freshness"] == "current"
        )
        assert new_result.json()["assessment_id"] != first["assessment_id"]
        assert saved_payload(pg_engine, first["assessment_id"]) == before


def test_source_access_revocation_blocks_new_and_historical_http_reads(pg_engine, tmp_path):
    seeded, _, payload = case(pg_engine, tmp_path, public=True)
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as client:
        response = client.post("/v1/assessments", json=payload)
        assert response.status_code == 200
        identity = response.json()["assessment_id"]
        before = saved_payload(pg_engine, identity)
        with pg_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE sources SET visibility='tenant', tenant_id=:tenant "
                    "WHERE source_id=:source"
                ),
                dict(tenant="fixture-other-tenant", source=seeded["source_id"]),
            )
        assert_problem(client.get("/v1/assessments/" + identity), 404, "not_found")
        assert_problem(client.post("/v1/assessments", json=payload), 404, "not_found")
        assert saved_payload(pg_engine, identity) == before


def test_cross_tenant_resources_and_unknown_resources_have_identical_public_error(
    pg_engine, tmp_path
):
    seeded, _, payload = case(pg_engine, tmp_path)
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as owner:
        result = owner.post("/v1/assessments", json=payload)
        assert result.status_code == 200
        identity = result.json()["assessment_id"]
    _, foreign_token = original.actor(pg_engine, "fixture-other-tenant", Role.ANALYST)
    with client_for(pg_engine, seeded["store"], foreign_token) as foreign:
        denied = foreign.get("/v1/assessments/" + identity)
        absent = foreign.get("/v1/assessments/" + str(uuid4()))
        for response in (denied, absent, foreign.post("/v1/assessments", json=payload)):
            assert_problem(response, 404, "not_found")
            assert seeded["tenant"] not in response.text
        assert denied.json()["error"] == absent.json()["error"]
        assert denied.json()["detail"] == absent.json()["detail"]


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_raw_integrity_and_unavailability_block_history_and_post_without_writes(
    pg_engine, tmp_path, damage
):
    seeded, _, payload = case(pg_engine, tmp_path)
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as client:
        result = client.post("/v1/assessments", json=payload)
        assert result.status_code == 200
        identity = result.json()["assessment_id"]
        before = saved_payload(pg_engine, identity)
        with pg_engine.connect() as connection:
            digest = connection.scalar(
                select(document_revisions.c.content_hash).where(
                    document_revisions.c.revision_id == seeded["revision_id"]
                )
            )
        if damage == "missing":
            seeded["store"].delete_object(digest)
            status, code = 503, "assessment_evidence_unavailable"
        else:
            seeded["store"].object_path_for_hash(digest).write_bytes(b"synthetic damaged CAS")
            status, code = 409, "assessment_inputs_invalid"
        count = original.count(pg_engine, assessment_results)
        for response in (
            client.get("/v1/assessments/" + identity),
            client.post("/v1/assessments", json=payload),
        ):
            assert_problem(response, status, code)
            assert digest not in response.text and str(tmp_path) not in response.text
        assert original.count(pg_engine, assessment_results) == count
        assert saved_payload(pg_engine, identity) == before


def test_pg_csrf_viewer_role_change_and_session_revocation(pg_engine, tmp_path):
    seeded, _, payload = case(pg_engine, tmp_path)
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as client:
        assert_problem(
            client.post("/v1/assessments", json=payload, headers={"X-CSRF-Token": "wrong"}),
            403,
            "csrf_rejected",
        )
        assert_problem(
            client.post(
                "/v1/assessments", json=payload, headers={"Origin": "http://untrusted.invalid"}
            ),
            403,
            "csrf_rejected",
        )
        with pg_engine.begin() as connection:
            connection.execute(
                update(users)
                .where(users.c.user_id == seeded["asset_actor"].user_id)
                .values(role="viewer")
            )
        assert_problem(client.post("/v1/assessments", json=payload), 403, "permission_denied")
        assert_problem(client.get("/v1/assessments/" + str(uuid4())), 403, "permission_denied")
        with pg_engine.begin() as connection:
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.user_id == seeded["asset_actor"].user_id)
                .values(revoked_at=datetime.now(UTC))
            )
        assert_problem(client.post("/v1/assessments", json=payload), 401, "session_expired")
        assert_problem(client.get("/v1/assessments/" + str(uuid4())), 401, "session_expired")


@pytest.mark.parametrize(
    "changing,status,code",
    [
        ("role", 403, "permission_denied"),
        ("source_acl", 404, "not_found"),
        ("raw", 409, "assessment_inputs_invalid"),
    ],
)
def test_http_commit_rechecks_inputs_after_actual_preparation(
    pg_engine, tmp_path, monkeypatch, changing, status, code
):
    seeded, _, payload = case(pg_engine, tmp_path, public=changing == "source_acl")
    prepare = AssessmentService.prepare
    count = original.count(pg_engine, assessment_results)

    def prepare_then_change(service, *arguments):
        prepared = prepare(service, *arguments)
        if changing == "raw":
            digest = prepared.inputs.sources[0].content_sha256
            seeded["store"].object_path_for_hash(digest).write_bytes(b"synthetic changed CAS")
        else:
            with pg_engine.begin() as connection:
                if changing == "role":
                    connection.execute(
                        update(users)
                        .where(users.c.user_id == seeded["asset_actor"].user_id)
                        .values(role="viewer")
                    )
                else:
                    connection.execute(
                        text(
                            "UPDATE sources SET visibility='tenant', tenant_id=:tenant "
                            "WHERE source_id=:source"
                        ),
                        dict(tenant="fixture-other-tenant", source=seeded["source_id"]),
                    )
        return prepared

    monkeypatch.setattr(AssessmentService, "prepare", prepare_then_change)
    with client_for(pg_engine, seeded["store"], seeded["asset_token"]) as client:
        assert_problem(client.post("/v1/assessments", json=payload), status, code)
    assert original.count(pg_engine, assessment_results) == count
