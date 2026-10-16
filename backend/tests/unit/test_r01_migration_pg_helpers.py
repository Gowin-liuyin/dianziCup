"""PG 测试辅助的纯负例，不解密凭据、不连接 PostgreSQL。"""

import inspect
import json
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import URL, Connection, Engine
from tests.integration import test_r01_migration_engine_disposal_pg as pg


def test_record_creates_missing_owned_log_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = tmp_path / "owned" / "missing"
    monkeypatch.setattr(pg, "RUN", run)
    pg.emit_record({"event": "explicit_synthetic_probe"})
    record = json.loads((run / "pg_lifecycle.jsonl").read_text())
    assert record["event"] == "explicit_synthetic_probe"


@dataclass
class CatalogState:
    exists: bool = False
    marker: str = ""
    drops: int = 0


def fake_fixture_engines(
    monkeypatch: pytest.MonkeyPatch, *, corrupt_marker: bool = False
) -> tuple[Mock, Mock, CatalogState]:
    state = CatalogState()
    control = Mock(spec=Connection)
    parent = Mock(spec=Engine)
    schema_engine = Mock(spec=Engine)
    parent.connect.return_value = nullcontext(control)
    schema_engine.begin.return_value = nullcontext(control)

    def execute(statement: object, parameters: object = None) -> Mock:
        query = str(statement)
        result = Mock()
        if "pg_backend_pid()" in query:
            result.one.return_value = ("test_dianzi_r01_20261014", "test_dianzi_r01", 123, "public")
        elif "current_database()" in query:
            result.one.return_value = ("test_dianzi_r01_20261014", "test_dianzi_r01")
        elif "shobj_description" in query:
            marker = "explicit_wrong_marker" if corrupt_marker else state.marker
            result.one.return_value = (456, marker)
        elif "rolsuper" in query:
            result.scalar_one.return_value = False
        elif "pg_stat_activity" in query:
            result.mappings.return_value = []
        elif "SELECT oid" in query:
            result.scalar_one.return_value = 456
            result.scalar_one_or_none.return_value = 456 if state.exists else None
        else:
            raise AssertionError("unexpected synthetic catalog query")
        return result

    def execute_ddl(statement: str) -> None:
        if statement.startswith("CREATE DATABASE"):
            state.exists = True
        elif statement.startswith("COMMENT ON DATABASE"):
            state.marker = statement.split(" IS '")[1][:-1]
        elif statement.startswith("DROP DATABASE"):
            state.exists = False
            state.drops += 1
        else:
            assert statement.startswith("CREATE SCHEMA")

    def create_engine(url: URL, **arguments: object) -> Engine:
        return parent if url.database == "test_dianzi_r01_20261014" else schema_engine

    control.execute.side_effect = execute
    control.exec_driver_sql.side_effect = execute_ddl
    monkeypatch.setattr(pg, "load_parent_url", synthetic_parent_url)
    monkeypatch.setattr(pg, "create_engine", create_engine)
    return parent, schema_engine, state


def synthetic_parent_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username="test_dianzi_r01",
        host="127.0.0.1",
        port=25432,
        database="test_dianzi_r01_20261014",
    )


def test_logging_failure_cannot_bypass_disposal_or_guarded_database_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent, schema_engine, state = fake_fixture_engines(monkeypatch)
    failure = PermissionError("explicit synthetic report IO failure")

    def failed_record(record: dict[str, object]) -> None:
        raise failure

    monkeypatch.setattr(pg, "emit_record", failed_record)
    factory: Callable[[], Iterator[pg.OwnedDatabase]] = inspect.unwrap(pg.owned_database)
    fixture = factory()
    next(fixture)
    with pytest.raises(RuntimeError, match="test report writes failed") as caught:
        next(fixture)
    assert caught.value.__cause__ is failure
    parent.dispose.assert_called_once()
    assert schema_engine.dispose.call_count == 2
    assert state.drops == 1
    assert state.exists is False


def test_marker_mismatch_blocks_drop_and_still_disposes_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent, _schema_engine, state = fake_fixture_engines(monkeypatch, corrupt_marker=True)
    monkeypatch.setattr(pg, "emit_record", lambda record: None)
    factory: Callable[[], Iterator[pg.OwnedDatabase]] = inspect.unwrap(pg.owned_database)
    fixture = factory()
    next(fixture)
    with pytest.raises(AssertionError):
        next(fixture)
    parent.dispose.assert_called_once()
    assert state.drops == 0
    assert state.exists is True


def test_disposal_callback_report_error_preserves_original_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned = pg.OwnedDatabase(
        Mock(spec=Engine),
        synthetic_parent_url(),
        "test_explicit_synthetic",
        "test_synthetic",
        "explicit_synthetic_marker",
        456,
    )
    report_failure = PermissionError("explicit synthetic dispose log failure")
    original_failure = RuntimeError("explicit synthetic original migration failure")

    def failed_record(record: dict[str, object]) -> None:
        raise report_failure

    def recorded_connection(
        connection: Connection, label: str, *, record: Callable[[dict[str, object]], None]
    ) -> int:
        return 123

    monkeypatch.setattr(pg, "emit_record", failed_record)
    monkeypatch.setattr(pg, "record_connection", recorded_connection)
    pg.trace_owned_engine(monkeypatch, owned, "explicit_synthetic_sqlite_memory")
    engine = pg.sqlalchemy.create_engine("sqlite://")
    with pytest.raises(RuntimeError) as caught:
        try:
            with engine.connect():
                raise original_failure
        finally:
            engine.dispose()
    assert caught.value is original_failure
    assert owned.reporting_errors == [report_failure]


def test_failure_node_prepares_head_before_installing_failure_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned = pg.OwnedDatabase(
        Mock(spec=Engine),
        synthetic_parent_url(),
        "test_explicit_synthetic",
        "test_synthetic",
        "explicit_synthetic_marker",
        456,
    )
    preparation = RuntimeError("explicit synthetic preparation boundary")
    revisions: list[str] = []

    def prepare_head(url: str, revision: str) -> None:
        revisions.append(revision)
        raise preparation

    def unexpected_probe(*arguments: object, **keywords: object) -> None:
        raise AssertionError("failure probe installed before head preparation")

    monkeypatch.setattr(pg, "run_migrations", prepare_head)
    monkeypatch.setattr(pg, "trace_owned_engine", unexpected_probe)
    with pytest.raises(RuntimeError) as caught:
        pg.test_migration_failure_rolls_back_and_disposes_without_replacing_exception(
            owned, monkeypatch, lambda secret: None
        )
    assert caught.value is preparation
    assert revisions == [pg.HEAD]
