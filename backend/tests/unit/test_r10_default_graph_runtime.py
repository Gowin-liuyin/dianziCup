"""Explicit offline transaction and driver fixtures test default consumer composition."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from pydantic import SecretStr

from ai_intel.domain.access import READ_PUBLIC, AccessScope, Role
from ai_intel.infrastructure.neo4j_projection import Neo4jProjectionStore
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge import default_graph_runtime as runtime
from ai_intel.knowledge.graph_projection import ProjectionDigestConflict
from ai_intel.workers.executor import (
    DetachedJobHandler,
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
)
from ai_intel.workers.jobs import JobLeaseLostError

NOW = datetime(2026, 10, 17, tzinfo=UTC)
PAYLOAD = b'{"change_id":"offline-fixture"}'
CONTEXT = JobExecutionContext(str(uuid4()), "offline-worker", 1, None)
PARTIAL = JobExecutionResult("partial", "pg:hybrid_receipt:fixture", "other_consumers_pending")
PUBLIC = AccessScope("offline-worker", None, Role.VIEWER, frozenset({READ_PUBLIC}))


def offline_batch():
    return MagicMock(namespace=runtime.DEFAULT_GRAPH_NAMESPACE)


def settings(configured=True):
    return ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        neo4j_uri="bolt://127.0.0.1:27687" if configured else None,
        neo4j_username="offline-fixture" if configured else None,
        neo4j_password=SecretStr("offline-fixture-only") if configured else None,
        opensearch_url=None,
        semantic_model_cache_directory=None,
    )


@pytest.fixture
def offline_factory(monkeypatch):
    driver = MagicMock()
    constructor = MagicMock(return_value=driver)
    monkeypatch.setattr(runtime.AsyncGraphDatabase, "driver", constructor)
    hybrid = MagicMock(return_value=PARTIAL)

    @contextmanager
    def projection_handlers(engine, configuration):
        yield {"knowledge_change": hybrid}

    monkeypatch.setattr(runtime, "build_projection_job_handlers", projection_handlers)
    return SimpleNamespace(driver=driver, constructor=constructor, hybrid=hybrid)


@pytest.fixture
def offline_transactions(monkeypatch, offline_factory):
    ledger = SimpleNamespace(durable=[], events=[], session_count=0)

    class OfflineSession:
        def __init__(self, engine):
            ledger.session_count += 1
            self.number = ledger.session_count
            self.pending = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        @contextmanager
        def begin(self):
            ledger.events.append((self.number, "begin"))
            try:
                yield
            except BaseException:
                ledger.events.append((self.number, "rollback"))
                raise
            else:
                ledger.durable.extend(self.pending)
                ledger.events.append((self.number, "commit"))

    def graph_policy(engine, store, authorize):
        def schedule(session, context, payload):
            authorize(session, context)
            ledger.events.append((session.number, "schedule"))
            if "one-generation" not in ledger.durable:
                session.pending.append("one-generation")
            return JobExecutionResult("partial", "pg:job:graph", "children_pending")

        return SimpleNamespace(knowledge_change_handler=schedule)

    def authorize(session, context, payload, job_type):
        ledger.events.append((session.number, "authorize"))
        return PUBLIC

    monkeypatch.setattr(runtime, "Session", OfflineSession)
    monkeypatch.setattr(runtime, "build_graph_runtime_policy", graph_policy)
    monkeypatch.setattr(runtime, "_authorize_task", authorize)
    ledger.authorize = authorize
    return ledger


def test_unconfigured_preserves_exact_hybrid_handler_and_never_constructs_driver(offline_factory):
    with runtime.build_default_graph_job_handlers(MagicMock(), settings(False)) as handlers:
        assert handlers["knowledge_change"] is offline_factory.hybrid
        assert set(handlers) == {
            "knowledge_change",
            "graph_reconcile",
            "graph_capture",
            "graph_apply",
        }
        assert handlers["knowledge_change"](MagicMock(), CONTEXT, PAYLOAD) is PARTIAL
    offline_factory.constructor.assert_not_called()


@pytest.mark.parametrize("job_type", ["graph_reconcile", "graph_capture", "graph_apply"])
def test_unconfigured_graph_jobs_remain_explicitly_blocked(offline_factory, job_type):
    with runtime.build_default_graph_job_handlers(MagicMock(), settings(False)) as handlers:
        with pytest.raises(JobExecutionError, match="graph_projection_not_configured") as failure:
            handlers[job_type](MagicMock(), CONTEXT, b"{}")
        assert failure.value.blocked
    offline_factory.constructor.assert_not_called()


def test_configured_driver_is_bounded_but_constructing_handlers_has_no_graph_io(offline_factory):
    with runtime.build_default_graph_job_handlers(MagicMock(), settings()) as handlers:
        assert isinstance(handlers["knowledge_change"], DetachedJobHandler)
        assert isinstance(handlers["graph_reconcile"], DetachedJobHandler)
        assert isinstance(handlers["graph_capture"], DetachedJobHandler)
        assert not isinstance(handlers["graph_apply"], DetachedJobHandler)
        offline_factory.driver.session.assert_not_called()
        offline_factory.driver.verify_connectivity.assert_not_called()
        options = offline_factory.constructor.call_args.kwargs
        assert options["max_connection_pool_size"] == 2
        assert options["max_transaction_retry_time"] == 0
        assert options["telemetry_disabled"] is True
        for field in (
            "connection_timeout",
            "connection_write_timeout",
            "connection_acquisition_timeout",
            "liveness_check_timeout",
        ):
            assert 0 < options[field] <= 3
    offline_factory.driver.close.assert_called_once_with()


@pytest.mark.parametrize("error", [RuntimeError("offline failure"), KeyboardInterrupt()])
def test_driver_closes_when_the_consumer_or_caller_is_interrupted(offline_factory, error):
    with (
        pytest.raises(type(error)),
        runtime.build_default_graph_job_handlers(MagicMock(), settings()),
    ):
        raise error
    offline_factory.driver.close.assert_called_once_with()


def test_graph_dispatch_commits_before_fresh_hybrid_and_returns_hybrid_result(
    offline_factory, offline_transactions
):
    ledger = offline_transactions

    def hybrid(session, context, payload):
        assert ledger.durable == ["one-generation"]
        assert session.number == 2
        assert ledger.events[-1] == (2, "authorize")
        return PARTIAL

    offline_factory.hybrid.side_effect = hybrid
    with runtime.build_default_graph_job_handlers(MagicMock(), settings()) as handlers:
        result = handlers["knowledge_change"].handler(CONTEXT, PAYLOAD)
    assert result is PARTIAL
    assert ledger.events == [
        (1, "begin"),
        (1, "authorize"),
        (1, "schedule"),
        (1, "commit"),
        (2, "begin"),
        (2, "authorize"),
        (2, "commit"),
    ]
    offline_factory.driver.session.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        JobExecutionError("corpus_projection_not_configured", blocked=True),
        JobExecutionError("corpus_projection_deadline_exceeded"),
        RuntimeError("offline hybrid failure"),
    ],
)
def test_hybrid_failure_propagates_after_durable_graph_dispatch_without_replay_growth(
    offline_factory, offline_transactions, failure
):
    offline_factory.hybrid.side_effect = failure
    with runtime.build_default_graph_job_handlers(MagicMock(), settings()) as handlers:
        for _ in range(2):
            with pytest.raises(type(failure)) as caught:
                handlers["knowledge_change"].handler(CONTEXT, PAYLOAD)
            assert caught.value is failure
    assert offline_transactions.durable == ["one-generation"]
    assert offline_transactions.session_count == 4
    assert offline_transactions.events[-1] == (4, "rollback")
    offline_factory.driver.close.assert_called_once_with()


def test_second_stage_lease_loss_keeps_graph_dispatch_and_never_calls_hybrid(
    monkeypatch, offline_factory, offline_transactions
):
    ledger = offline_transactions

    def authorize(session, context, payload, job_type):
        if session.number == 2:
            raise JobLeaseLostError("job lease unavailable")
        return ledger.authorize(session, context, payload, job_type)

    monkeypatch.setattr(runtime, "_authorize_task", authorize)
    with (
        runtime.build_default_graph_job_handlers(MagicMock(), settings()) as handlers,
        pytest.raises(JobLeaseLostError),
    ):
        handlers["knowledge_change"].handler(CONTEXT, PAYLOAD)
    assert ledger.durable == ["one-generation"]
    assert ledger.events[-1] == (2, "rollback")
    offline_factory.hybrid.assert_not_called()


def test_first_stage_failure_rolls_back_dispatch_and_never_calls_hybrid(
    monkeypatch, offline_factory, offline_transactions
):
    monkeypatch.setattr(
        runtime,
        "_authorize_task",
        MagicMock(side_effect=JobExecutionError("scope_denied", blocked=True)),
    )
    with (
        runtime.build_default_graph_job_handlers(MagicMock(), settings()) as handlers,
        pytest.raises(JobExecutionError, match="scope_denied"),
    ):
        handlers["knowledge_change"].handler(CONTEXT, PAYLOAD)
    assert offline_transactions.durable == []
    assert offline_transactions.events == [(1, "begin"), (1, "rollback")]
    offline_factory.hybrid.assert_not_called()


def test_schema_is_lazy_and_initialized_only_once_per_successful_store(
    monkeypatch, offline_factory
):
    initialize = MagicMock()
    apply = MagicMock(return_value="offline-receipt")
    monkeypatch.setattr(Neo4jProjectionStore, "initialize_schema", initialize)
    monkeypatch.setattr(Neo4jProjectionStore, "apply_batch", apply)
    store = runtime._SchemaInitializedProjectionStore(offline_factory.driver)
    initialize.assert_not_called()
    assert store.apply_batch(offline_batch(), "a" * 64) == "offline-receipt"
    assert store.apply_batch(offline_batch(), "a" * 64) == "offline-receipt"
    initialize.assert_called_once_with()
    assert apply.call_count == 2


@pytest.mark.parametrize("stage", ["schema", "apply"])
@pytest.mark.parametrize(
    "failure", [ServiceUnavailable("fixture-private"), Neo4jError("fixture-private")]
)
def test_graph_dependency_errors_are_safe_retryable_errors(
    monkeypatch, offline_factory, stage, failure
):
    initialize = MagicMock(side_effect=failure if stage == "schema" else None)
    apply = MagicMock(side_effect=failure if stage == "apply" else None)
    monkeypatch.setattr(Neo4jProjectionStore, "initialize_schema", initialize)
    monkeypatch.setattr(Neo4jProjectionStore, "apply_batch", apply)
    store = runtime._SchemaInitializedProjectionStore(offline_factory.driver)
    with pytest.raises(JobExecutionError, match=r"^graph_projection_unavailable$") as caught:
        store.apply_batch(offline_batch(), "a" * 64)
    assert not caught.value.blocked and not caught.value.permanent
    if stage == "schema":
        assert not store.schema_initialized
        apply.assert_not_called()


def test_projection_digest_conflicts_keep_existing_business_error(monkeypatch, offline_factory):
    monkeypatch.setattr(Neo4jProjectionStore, "initialize_schema", MagicMock())
    failure = ProjectionDigestConflict("graph_projection_digest_conflict")
    monkeypatch.setattr(Neo4jProjectionStore, "apply_batch", MagicMock(side_effect=failure))
    store = runtime._SchemaInitializedProjectionStore(offline_factory.driver)
    with pytest.raises(ProjectionDigestConflict) as caught:
        store.apply_batch(offline_batch(), "a" * 64)
    assert caught.value is failure


def test_factory_finally_closes_driver_when_graph_apply_fails(monkeypatch, offline_factory):
    monkeypatch.setattr(
        Neo4jProjectionStore,
        "initialize_schema",
        MagicMock(side_effect=ServiceUnavailable("private")),
    )
    with (
        pytest.raises(JobExecutionError, match="graph_projection_unavailable"),
        runtime.build_default_graph_job_handlers(MagicMock(), settings()),
    ):
        runtime._SchemaInitializedProjectionStore(offline_factory.driver).apply_batch(
            offline_batch(), "a" * 64
        )
    offline_factory.driver.close.assert_called_once_with()


def test_completion_guard_revalidates_scope_and_does_not_infer_global_completion(
    monkeypatch, offline_factory, offline_transactions
):
    failure = JobExecutionError("graph_projection_scope_denied", blocked=True)
    with runtime.build_default_graph_job_handlers(MagicMock(), settings()) as handlers:
        result = handlers["knowledge_change"].handler(CONTEXT, PAYLOAD)
        monkeypatch.setattr(runtime, "_authorize_task", MagicMock(side_effect=failure))
        with pytest.raises(JobExecutionError) as caught:
            handlers["knowledge_change"].completion_guard(MagicMock(), CONTEXT, PAYLOAD, result)
        assert caught.value is failure
    assert result.outcome == "partial"
    assert offline_transactions.durable == ["one-generation"]


def test_canonical_lease_helper_uses_database_time_instead_of_host_clock(monkeypatch):
    session = MagicMock()
    session.scalar.side_effect = [NOW, NOW + timedelta(seconds=1)]
    lease = MagicMock(
        return_value={
            "job_type": "knowledge_change",
            "tenant_id": None,
            "lease_expires_at": NOW + timedelta(seconds=60),
        }
    )
    monkeypatch.setattr(runtime, "require_job_lease", lease)
    monkeypatch.setattr(runtime, "read_job_payload", MagicMock(return_value=PAYLOAD))
    scope = runtime._authorize_task(session, CONTEXT, PAYLOAD, "knowledge_change")
    assert lease.call_args.args[3] == NOW
    assert lease.call_args.kwargs == {"expected_attempt": 1}
    assert scope.permissions == frozenset({READ_PUBLIC})
