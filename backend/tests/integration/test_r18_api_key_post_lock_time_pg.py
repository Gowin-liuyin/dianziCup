"""Owned real PostgreSQL waits; the original UTC expiry probe is replayed separately unchanged."""

from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select, text, update
from test_r18_api_key_credentials_pg import NOW, PgCase, ProcessInput, _rate_worker
from test_r18_api_key_credentials_pg import owned_database as owned_database
from test_r18_api_key_credentials_pg import pg_case as pg_case

from ai_intel.api.credential_models import api_key_rate_buckets
from ai_intel.api.credentials import (
    ApiKeyCredential,
    InvalidApiKeyError,
    PgApiKeyService,
    consume_api_key_rate_limit,
    lock_authenticated_principal,
)
from ai_intel.domain.access import AccessScope
from ai_intel.knowledge.models import users

pytestmark = pytest.mark.real_pg


def wait_for_lock(pg_case: PgCase, reader_pid: list[int]) -> None:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if reader_pid:
            with pg_case.engine.connect() as connection:
                if (
                    connection.scalar(
                        text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                        {"pid": reader_pid[0]},
                    )
                    == "Lock"
                ):
                    return
        time.sleep(0.01)
    raise AssertionError("reader did not reach an actual PostgreSQL lock wait")


def test_real_owner_lock_wait_before_expiry_returns_current_tenant(pg_case: PgCase) -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=3)
    issued = PgApiKeyService(pg_case.engine).issue_key(
        pg_case.session, frozenset({"read:public"}), expires_at=expires_at
    )
    reader_pid: list[int] = []

    def authenticate() -> AccessScope:
        with pg_case.engine.begin() as connection:
            reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            return lock_authenticated_principal(
                connection, ApiKeyCredential(issued.token), datetime.now(UTC)
            )

    with pg_case.engine.begin() as holding, ThreadPoolExecutor(max_workers=1) as executor:
        holding.execute(
            update(users)
            .where(users.c.user_id == issued.metadata.user_id)
            .values(tenant_id="synthetic-post-wait-tenant")
        )
        future = executor.submit(authenticate)
        wait_for_lock(pg_case, reader_pid)
        assert not future.done()
        holding.commit()
        scope = future.result(timeout=6)
    assert datetime.now(UTC) < expires_at
    assert scope.tenant_id == "synthetic-post-wait-tenant"
    assert scope.permissions == frozenset({"read:public"})


def test_real_quota_bucket_wait_crossing_expiry_cannot_consume(pg_case: PgCase) -> None:
    current = datetime.now(UTC)
    if current.second >= 55:
        time.sleep(60 - current.second - current.microsecond / 1_000_000 + 0.1)
    expires_at = datetime.now(UTC) + timedelta(seconds=3)
    issued = PgApiKeyService(pg_case.engine).issue_key(
        pg_case.session, frozenset({"read:public"}), expires_at=expires_at
    )
    window = datetime.now(UTC).replace(second=0, microsecond=0)
    bucket_filter = (
        api_key_rate_buckets.c.key_id == issued.metadata.key_id,
        api_key_rate_buckets.c.operation == "ask",
        api_key_rate_buckets.c.window_started_at == window,
    )
    with pg_case.engine.begin() as connection:
        connection.execute(
            insert(api_key_rate_buckets).values(
                key_id=issued.metadata.key_id,
                operation="ask",
                window_started_at=window,
                request_count=0,
            )
        )
    reader_pid: list[int] = []

    def consume() -> AccessScope:
        with pg_case.engine.begin() as connection:
            reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            return consume_api_key_rate_limit(
                connection, ApiKeyCredential(issued.token), datetime.now(UTC), operation="ask"
            )

    with pg_case.engine.begin() as holding, ThreadPoolExecutor(max_workers=1) as executor:
        holding.execute(update(api_key_rate_buckets).where(*bucket_filter).values(request_count=0))
        future = executor.submit(consume)
        wait_for_lock(pg_case, reader_pid)
        assert not future.done()
        remaining = (expires_at - datetime.now(UTC)).total_seconds() + 0.1
        if remaining > 0:
            time.sleep(remaining)
        holding.commit()
        with pytest.raises(InvalidApiKeyError):
            future.result(timeout=6)
    with pg_case.engine.connect() as connection:
        assert (
            connection.scalar(select(api_key_rate_buckets.c.request_count).where(*bucket_filter))
            == 0
        )


def test_real_bucket_wait_advances_trusted_fixture_epoch_to_new_minute(pg_case: PgCase) -> None:
    """Use the historical server epoch with real lock waiting; wall clocks remain unchanged."""
    issued = pg_case.issue()
    server_now = NOW.replace(second=59, microsecond=500000)
    window = server_now.replace(second=0, microsecond=0)
    bucket_filter = (
        api_key_rate_buckets.c.key_id == issued.metadata.key_id,
        api_key_rate_buckets.c.operation == "ask",
        api_key_rate_buckets.c.window_started_at == window,
    )
    with pg_case.engine.begin() as connection:
        connection.execute(
            insert(api_key_rate_buckets).values(
                key_id=issued.metadata.key_id,
                operation="ask",
                window_started_at=window,
                request_count=10,
            )
        )
    reader_pid: list[int] = []

    def consume() -> AccessScope:
        with pg_case.engine.begin() as connection:
            reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            return consume_api_key_rate_limit(
                connection, ApiKeyCredential(issued.token), server_now, operation="ask"
            )

    with pg_case.engine.begin() as holding, ThreadPoolExecutor(max_workers=1) as executor:
        holding.execute(update(api_key_rate_buckets).where(*bucket_filter).values(request_count=10))
        future = executor.submit(consume)
        wait_for_lock(pg_case, reader_pid)
        assert not future.done()
        time.sleep(0.7)
        holding.commit()
        assert future.result(timeout=6).user_id == issued.metadata.user_id
    with pg_case.engine.connect() as connection:
        buckets = list(
            connection.execute(
                select(
                    api_key_rate_buckets.c.window_started_at, api_key_rate_buckets.c.request_count
                )
                .where(api_key_rate_buckets.c.key_id == issued.metadata.key_id)
                .order_by(api_key_rate_buckets.c.window_started_at)
            ).tuples()
        )
    assert buckets == [(window, 10), (window + timedelta(minutes=1), 1)]


def test_three_spawn_processes_share_twelve_ask_attempts_as_ten_and_two(pg_case: PgCase) -> None:
    issued = pg_case.issue()
    context = multiprocessing.get_context("spawn")
    processes = []
    pipes = []
    try:
        for _ in range(3):
            parent, child = context.Pipe()
            process = context.Process(target=_rate_worker, args=(child,))
            process.start()
            child.close()
            processes.append(process)
            pipes.append(parent)
            parent.send(
                ProcessInput(
                    pg_case.database_url,
                    pg_case.schema,
                    NOW,
                    ApiKeyCredential(issued.token),
                    "ask",
                    4,
                )
            )
        for pipe in pipes:
            assert pipe.poll(15) and pipe.recv() == "ready"
        for pipe in pipes:
            pipe.send("go")
        outcomes = []
        for pipe in pipes:
            assert pipe.poll(20)
            outcomes.append(pipe.recv())
        assert sum(committed for committed, _ in outcomes) == 10
        assert sum(limited for _, limited in outcomes) == 2
        for process in processes:
            process.join(5)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        for pipe in pipes:
            pipe.close()
