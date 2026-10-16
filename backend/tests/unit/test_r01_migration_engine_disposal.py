"""迁移拥有的 Engine 在成功与异常退出时均释放，原异常保持。"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from runpy import run_path

import pytest
import sqlalchemy
from alembic import context
from alembic.config import Config

from ai_intel.infrastructure import database

MIGRATION_ENV = Path(__file__).resolve().parents[2] / "migrations" / "env.py"


@pytest.mark.parametrize("failure_phase", [None, "connect", "migration"])
def test_online_migration_disposes_owned_engine_and_preserves_failure(
    monkeypatch: pytest.MonkeyPatch, failure_phase: str | None
) -> None:
    events: list[str] = []
    failure = RuntimeError("explicit synthetic migration failure")
    connection = object()
    configuration = Config()
    configuration.set_main_option("sqlalchemy.url", "postgresql://synthetic/test_lifecycle")

    class OwnedEngine:
        @contextmanager
        def connect(self) -> Iterator[object]:
            events.append("connect")
            if failure_phase == "connect":
                raise failure
            try:
                yield connection
            finally:
                events.append("connection_exit")

        def dispose(self) -> None:
            events.append("dispose")

    engine = OwnedEngine()

    def create_owned_engine(url: str) -> OwnedEngine:
        assert url == "postgresql://synthetic/test_lifecycle"
        events.append("create_engine")
        return engine

    def configure(*, connection: object) -> None:
        events.append("configure")

    @contextmanager
    def begin_transaction() -> Iterator[None]:
        events.append("transaction_enter")
        try:
            yield
        finally:
            events.append("transaction_exit")

    def migrate() -> None:
        events.append("run_migrations")
        if failure_phase == "migration":
            raise failure

    monkeypatch.setattr(sqlalchemy, "create_engine", create_owned_engine)
    monkeypatch.setattr(context, "config", configuration, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(context, "configure", configure)
    monkeypatch.setattr(context, "begin_transaction", begin_transaction)
    monkeypatch.setattr(context, "run_migrations", migrate)

    if failure_phase is None:
        run_path(str(MIGRATION_ENV))
    else:
        with pytest.raises(RuntimeError) as caught:
            run_path(str(MIGRATION_ENV))
        assert caught.value is failure

    expected = ["create_engine", "connect"]
    if failure_phase != "connect":
        expected += [
            "configure",
            "transaction_enter",
            "run_migrations",
            "transaction_exit",
            "connection_exit",
        ]
    assert events == [*expected, "dispose"]


@pytest.mark.parametrize("outcome", ["missing_table", "head", "query_failure"])
def test_revision_lookup_disposes_owned_engine_and_preserves_failure(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    events: list[str] = []
    failure = RuntimeError("explicit synthetic revision query failure")

    class QueryResult:
        def __init__(self, result: str | None) -> None:
            self.result = result

        def scalar(self) -> str | None:
            return self.result

    class RevisionConnection:
        def execute(
            self, statement: object, parameters: dict[str, str] | None = None
        ) -> QueryResult:
            events.append("query")
            if outcome == "query_failure":
                raise failure
            if parameters is not None:
                return QueryResult(None if outcome == "missing_table" else "alembic_version")
            return QueryResult("0030_revalidation_actor_bindings")

    class OwnedEngine:
        @contextmanager
        def connect(self) -> Iterator[RevisionConnection]:
            try:
                yield RevisionConnection()
            finally:
                events.append("connection_exit")

        def dispose(self) -> None:
            events.append("dispose")

    def create_owned_engine(url: str) -> OwnedEngine:
        assert url == "postgresql://synthetic/test_revision"
        return OwnedEngine()

    monkeypatch.setattr(database, "create_engine", create_owned_engine)
    if outcome == "query_failure":
        with pytest.raises(RuntimeError) as caught:
            database.current_migration_revision("postgresql://synthetic/test_revision")
        assert caught.value is failure
    else:
        expected = None if outcome == "missing_table" else "0030_revalidation_actor_bindings"
        assert (
            database.current_migration_revision("postgresql://synthetic/test_revision") == expected
        )
    query_count = 2 if outcome == "head" else 1
    assert events == [*(["query"] * query_count), "connection_exit", "dispose"]
