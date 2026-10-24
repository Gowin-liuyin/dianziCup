"""Marked async driver fixtures test lifecycle deadlines without PostgreSQL or network IO."""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from neo4j import AsyncDriver, AsyncResult, AsyncSession, AsyncTransaction

from ai_intel.infrastructure.neo4j_projection import Neo4jProjectionStore


@pytest.fixture
def async_fixture():
    driver = MagicMock(spec=AsyncDriver)
    session = MagicMock(spec=AsyncSession)
    transaction = MagicMock(spec=AsyncTransaction)
    result = MagicMock(spec=AsyncResult)
    driver.session.return_value = session
    driver.close = AsyncMock()
    session.begin_transaction = AsyncMock(return_value=transaction)
    session.close = AsyncMock()
    transaction.run = AsyncMock(return_value=result)
    transaction.commit = AsyncMock()
    transaction.rollback = AsyncMock()
    transaction.close = AsyncMock()
    result.consume = AsyncMock(return_value=object())
    result.single = AsyncMock(return_value={"count": 1})
    result.data = AsyncMock(return_value=[{"count": 1}])
    return driver, session, transaction, result


async def no_reply(*args, **kwargs):
    await asyncio.Event().wait()


def test_official_async_ports_execute_serially_and_close_on_one_owned_loop(async_fixture):
    driver, session, transaction, _ = async_fixture
    store = Neo4jProjectionStore(driver, timeout_seconds=0.1)
    try:
        with store._transaction() as current:
            answer = current.run("RETURN $value", {"value": 1})
            assert answer.single() == {"count": 1}
            assert answer.data() == [{"count": 1}]
            answer.consume()
        transaction.commit.assert_awaited_once()
        transaction.close.assert_awaited_once()
        session.close.assert_awaited_once()
        session.cancel.assert_not_called()
    finally:
        store.close_driver()
    assert store.driver_closed
    driver.close.assert_awaited_once()


@pytest.mark.parametrize("stage", ["begin", "run", "consume", "commit", "rollback"])
def test_one_session_deadline_cancels_stalled_io_and_never_returns_success(async_fixture, stage):
    driver, session, transaction, result = async_fixture
    delayed = {
        "begin": session.begin_transaction,
        "run": transaction.run,
        "consume": result.consume,
        "commit": transaction.commit,
        "rollback": transaction.rollback,
    }[stage]
    delayed.side_effect = no_reply
    store = Neo4jProjectionStore(driver, timeout_seconds=0.04)
    started = time.monotonic()
    returned = False
    try:
        with pytest.raises(TimeoutError), store._transaction() as current:
            current.run("RETURN $value", {"value": 1}).consume()
            if stage == "rollback":
                raise ValueError("synthetic business rejection")
        returned = True
        assert session.cancel.called
        assert session.close.await_count == 1
        assert time.monotonic() - started < 0.5
    finally:
        store.close_driver()
    assert returned and store.driver_closed
    if stage in {"begin", "run", "consume", "rollback"}:
        transaction.commit.assert_not_awaited()


@pytest.mark.parametrize("stage", ["transaction_close", "session_close", "driver_close"])
def test_cleanup_io_has_a_finite_cancellation_budget(async_fixture, stage):
    driver, session, transaction, _ = async_fixture
    delayed = {
        "transaction_close": transaction.close,
        "session_close": session.close,
        "driver_close": driver.close,
    }[stage]
    delayed.side_effect = no_reply
    store = Neo4jProjectionStore(driver, timeout_seconds=0.04)
    started = time.monotonic()
    if stage == "driver_close":
        with pytest.raises(TimeoutError):
            store.close_driver()
    else:
        try:
            with pytest.raises(TimeoutError), store._transaction():
                pass
            assert session.cancel.called
        finally:
            store.close_driver()
    assert time.monotonic() - started < 0.5
    assert store.driver_closed


def test_repeated_driver_close_does_not_start_a_new_loop_or_repeat_driver_io(async_fixture):
    driver, _, _, _ = async_fixture
    store = Neo4jProjectionStore(driver, timeout_seconds=0.1)
    store.close_driver()
    store.close_driver()
    driver.close.assert_awaited_once()
    assert store.driver_closed


def test_other_thread_is_rejected_before_session_or_driver_io(async_fixture):
    driver, _, _, _ = async_fixture
    store = Neo4jProjectionStore(driver, timeout_seconds=0.1)
    errors = []

    def use_from_other_thread():
        for action in (store.initialize_schema, store.close_driver):
            try:
                action()
            except RuntimeError as error:
                errors.append(str(error))

    thread = threading.Thread(target=use_from_other_thread)
    thread.start()
    thread.join(timeout=0.5)
    assert not thread.is_alive()
    assert errors == ["neo4j_projection_owner_thread_changed"] * 2
    driver.session.assert_not_called()
    driver.close.assert_not_called()
    store.close_driver()


def test_active_event_loop_is_rejected_without_starting_nested_runner_or_io(async_fixture):
    driver, _, _, _ = async_fixture
    store = Neo4jProjectionStore(driver, timeout_seconds=0.1)

    async def call_from_loop():
        with pytest.raises(RuntimeError, match="neo4j_projection_active_event_loop"):
            Neo4jProjectionStore(driver, timeout_seconds=0.1)
        for action in (store.initialize_schema, store.close_driver):
            with pytest.raises(RuntimeError, match="neo4j_projection_active_event_loop"):
                action()

    asyncio.run(call_from_loop())
    driver.session.assert_not_called()
    driver.close.assert_not_called()
    store.close_driver()


def test_original_business_rejection_rolls_back_closes_and_preserves_exception(async_fixture):
    driver, session, transaction, _ = async_fixture
    store = Neo4jProjectionStore(driver, timeout_seconds=0.1)
    original = ValueError("synthetic business rejection")
    try:
        with pytest.raises(ValueError) as caught, store._transaction():
            raise original
        assert caught.value is original
        transaction.rollback.assert_awaited_once()
        transaction.commit.assert_not_awaited()
        transaction.close.assert_awaited_once()
        session.close.assert_awaited_once()
    finally:
        store.close_driver()


def test_legacy_sync_driver_keeps_existing_transaction_protocol_and_closure():
    driver = MagicMock()
    session = driver.session.return_value
    transaction = session.begin_transaction.return_value
    store = Neo4jProjectionStore(driver)
    with store._transaction():
        pass
    transaction.commit.assert_called_once()
    transaction.close.assert_called_once()
    session.close.assert_called_once()
    store.close_driver()
    driver.close.assert_called_once()
    assert store.runner is None
