"""Synthetic IO boundaries exercise the real CI fixture entry without opening PostgreSQL."""

from __future__ import annotations

import importlib.util
import secrets
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.pool import NullPool


def _load_pg_fixture() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "integration/test_r18_api_key_credentials_pg.py"
    spec = importlib.util.spec_from_file_location("r18_ci_pg_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PG_FIXTURE = _load_pg_fixture()
owned_database = PG_FIXTURE.owned_database


@pytest.fixture(autouse=True)
def synthetic_ci_environment(monkeypatch: pytest.MonkeyPatch) -> SecretStr:
    run_id = "r01_ci_fixture1"
    database_url = SecretStr(
        URL.create(
            "postgresql+psycopg",
            username="test_ci",
            password=secrets.token_urlsafe(32),
            host="127.0.0.1",
            port=25436,
            database="test_dianzi_" + run_id,
        ).render_as_string(hide_password=False)
    )
    monkeypatch.setenv("DIANZI_TEST_RUN_ID", run_id)
    monkeypatch.setenv("TEST_DATABASE_URL", database_url.get_secret_value())
    return database_url


@pytest.fixture(autouse=True)
def synthetic_pg_boundary(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    engine = MagicMock(spec=Engine)
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.one.return_value = ("test_dianzi_r01_ci_fixture1", "test_ci")
    monkeypatch.setattr(PG_FIXTURE, "create_engine", MagicMock(return_value=engine))
    monkeypatch.setattr(PG_FIXTURE.metadata, "create_all", MagicMock())
    return engine


def test_ci_resource_fixture_uses_configured_isolated_url(
    owned_database: tuple[SecretStr, str],
    synthetic_ci_environment: SecretStr,
) -> None:
    """Pytest resolves the unchanged common guard and then the API-key owned-schema fixture."""
    database_url, schema = owned_database
    assert database_url == synthetic_ci_environment
    assert PG_FIXTURE.create_engine.call_args.args == (synthetic_ci_environment.get_secret_value(),)
    assert PG_FIXTURE.create_engine.call_args.kwargs["poolclass"] is NullPool
    assert schema.startswith("r18c_") and UUID(schema.removeprefix("r18c_")).version == 4


def test_owned_schema_cleanup_and_secret_registration(
    isolated_test_database_url: str,
    synthetic_pg_boundary: MagicMock,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    registered: list[SecretStr] = []

    def register(value: SecretStr) -> None:
        register_sensitive_failure_value(value)
        registered.append(value)

    fixture = PG_FIXTURE.owned_database.__wrapped__(isolated_test_database_url, register)
    database_url, schema = next(fixture)
    connection = synthetic_pg_boundary.begin.return_value.__enter__.return_value
    assert registered[0] == database_url and len(registered) == 2
    assert connection.exec_driver_sql.call_args.args == (f'CREATE SCHEMA "{schema}"',)
    fixture.close()
    assert connection.exec_driver_sql.call_args.args == (f'DROP SCHEMA "{schema}" CASCADE',)
    synthetic_pg_boundary.dispose.assert_called_once_with()


def test_plain_postgresql_scheme_uses_the_locked_psycopg_driver(
    synthetic_ci_environment: SecretStr,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plain_url = make_url(synthetic_ci_environment.get_secret_value()).set(drivername="postgresql")
    monkeypatch.setenv("TEST_DATABASE_URL", plain_url.render_as_string(hide_password=False))
    database_url, _schema = request.getfixturevalue("owned_database")
    assert database_url == synthetic_ci_environment
    assert PG_FIXTURE.create_engine.call_args.args == (synthetic_ci_environment.get_secret_value(),)


@pytest.mark.parametrize("failure_stage", ["identity", "create", "tables", "cleanup"])
def test_setup_or_cleanup_failure_never_touches_unowned_schema_and_disposes(
    failure_stage: str,
    isolated_test_database_url: str,
    synthetic_pg_boundary: MagicMock,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    connection = synthetic_pg_boundary.begin.return_value.__enter__.return_value
    if failure_stage == "identity":
        connection.execute.return_value.one.return_value = ("unowned_database", "unowned_user")
    elif failure_stage == "create":
        connection.exec_driver_sql.side_effect = RuntimeError("synthetic schema collision")
    elif failure_stage == "tables":
        PG_FIXTURE.metadata.create_all.side_effect = RuntimeError("synthetic table setup failure")
    fixture = PG_FIXTURE.owned_database.__wrapped__(
        isolated_test_database_url, register_sensitive_failure_value
    )
    if failure_stage == "cleanup":
        next(fixture)
        connection.exec_driver_sql.side_effect = RuntimeError("synthetic cleanup failure")
        with pytest.raises(RuntimeError, match="synthetic cleanup failure"):
            fixture.close()
    else:
        with pytest.raises(RuntimeError):
            next(fixture)
        assert all(
            "DROP SCHEMA" not in call.args[0] for call in connection.exec_driver_sql.call_args_list
        )
    synthetic_pg_boundary.dispose.assert_called_once_with()


@pytest.mark.parametrize("missing_name", ["TEST_DATABASE_URL", "DIANZI_TEST_RUN_ID"])
def test_missing_ci_resource_configuration_fails_closed_before_engine_creation(
    missing_name: str,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(missing_name)
    with pytest.raises(pytest.UsageError, match="blocked:"):
        request.getfixturevalue("owned_database")
    PG_FIXTURE.create_engine.assert_not_called()


@pytest.mark.parametrize(
    "changed_field,value",
    [
        ("database", "development"),
        ("database", "test_unmarked"),
        ("host", "production.example.invalid"),
        ("port", 5432),
        ("username", "application"),
    ],
)
def test_unmarked_or_non_test_resource_fails_closed_before_engine_creation(
    changed_field: str,
    value: str | int,
    synthetic_ci_environment: SecretStr,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = make_url(synthetic_ci_environment.get_secret_value())
    if changed_field == "port":
        assert isinstance(value, int)
        changed_url = original.set(port=value)
    else:
        assert isinstance(value, str)
        if changed_field == "database":
            changed_url = original.set(database=value)
        elif changed_field == "host":
            changed_url = original.set(host=value)
        else:
            changed_url = original.set(username=value)
    monkeypatch.setenv("TEST_DATABASE_URL", changed_url.render_as_string(hide_password=False))
    with pytest.raises(pytest.UsageError, match="blocked:"):
        request.getfixturevalue("owned_database")
    PG_FIXTURE.create_engine.assert_not_called()


def test_each_fixture_invocation_owns_a_distinct_schema(
    isolated_test_database_url: str,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    first: Generator[tuple[SecretStr, str], None, None] = PG_FIXTURE.owned_database.__wrapped__(
        isolated_test_database_url, register_sensitive_failure_value
    )
    second: Generator[tuple[SecretStr, str], None, None] = PG_FIXTURE.owned_database.__wrapped__(
        isolated_test_database_url, register_sensitive_failure_value
    )
    try:
        assert next(first)[1] != next(second)[1]
    finally:
        first.close()
        second.close()
