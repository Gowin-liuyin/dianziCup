"""The original Celery app gains only owned stop and source row fences."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from owned_stop_watcher import current_windows_identity

PRE_READY_PHASES = (
    "entry",
    "authorization",
    "role",
    "product_import",
    "settings",
    "service_urls",
    "engine",
    "database_session",
    "database_connect",
    "database_identity",
    "ready_publish",
)
PRE_READY_DIRECTORY = Path(__file__).resolve().parent / "pre_ready"
PRE_READY_RECEIPT_LIMIT_BYTES = 1024
PreReadyStatus = Literal["entered", "completed", "failed"]
ProcessRole = Literal["worker", "beat"]


def _write_pre_ready_phase(
    phase: str, status: PreReadyStatus, role: ProcessRole | None = None
) -> None:
    """Publish one bounded immutable self-identity receipt without diagnostic values."""
    if phase not in PRE_READY_PHASES or status not in ("entered", "completed", "failed"):
        raise ValueError("unknown pre-ready phase")
    if role not in (None, "worker", "beat"):
        raise ValueError("unknown pre-ready role")
    directory = Path(__file__).resolve().parent / "pre_ready"
    if directory != PRE_READY_DIRECTORY or directory.resolve() != directory:
        raise ValueError("pre-ready directory identity differs")
    for parent in (directory, *directory.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("pre-ready directory is redirected")
    identity = current_windows_identity()
    actual_pid = identity["actual_pid"]
    creation_ticks = identity["creation_ticks"]
    if (
        type(actual_pid) is not int
        or actual_pid != os.getpid()
        or type(creation_ticks) is not int
        or creation_ticks <= 0
    ):
        raise ValueError("pre-ready self identity differs")
    payload = (
        json.dumps(
            {
                "schema_version": 1,
                "phase": phase,
                "status": status,
                "role": role,
                "actual_pid": actual_pid,
                "creation_ticks": creation_ticks,
                "observed_at": datetime.now(UTC).isoformat(),
            },
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    if len(payload) > PRE_READY_RECEIPT_LIMIT_BYTES:
        raise RuntimeError("pre-ready receipt budget exceeded")
    directory.mkdir(exist_ok=True)
    phase_number = PRE_READY_PHASES.index(phase)
    path = directory / f"{actual_pid}_{creation_ticks}_{phase_number:02}_{phase}_{status}.json"
    pending = path.with_suffix(".pending")
    with pending.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    os.link(pending, path)
    pending.unlink()


@contextmanager
def _pre_ready_stage(phase: str, role: ProcessRole | None) -> Iterator[None]:
    """Keep failed stages distinct from completed stages and propagate every failure."""
    _write_pre_ready_phase(phase, "entered", role)
    try:
        yield
    except Exception:
        _write_pre_ready_phase(phase, "failed", role)
        raise
    else:
        _write_pre_ready_phase(phase, "completed", role)


_write_pre_ready_phase("entry", "completed")

if TYPE_CHECKING:
    from celery import Celery


def load_owned_application() -> Celery:
    _write_pre_ready_phase("authorization", "entered")
    from authorization import verify_live_authorization
    from run_binding import (
        QUEUE,
        REDIS_PREFIX,
        require_cumulative_producer_slot,
        validate_service_urls,
        verify_database_connection,
    )

    binding = verify_live_authorization()
    _write_pre_ready_phase("authorization", "completed")

    from owned_stop_watcher import install_owned_stop_watcher

    with _pre_ready_stage("role", None):
        raw_role = os.environ.get("DIANZI_OWNED_PROCESS_ROLE")
        if raw_role == "worker":
            role: ProcessRole = "worker"
        elif raw_role == "beat":
            role = "beat"
        else:
            raise RuntimeError("owned source process role required")

    with _pre_ready_stage("product_import", role):
        from ai_intel.infrastructure.database import build_engine
        from ai_intel.infrastructure.settings import load_application_settings
        from sqlalchemy import text
        from task_fence import require_producer_slot

    with _pre_ready_stage("settings", role):
        settings = load_application_settings()
        if (
            not settings.source_polling_enabled
            or settings.data_mode != "live"
            or settings.content_store_backend != "minio"
        ):
            raise RuntimeError("live source configuration differs from reviewed scope")
        if settings.generation_api_key and settings.generation_api_key.get_secret_value():
            raise RuntimeError("model requests are not authorized")
    with _pre_ready_stage("service_urls", role):
        validate_service_urls(
            settings.database_url.get_secret_value() if settings.database_url else None,
            settings.redis_url.get_secret_value() if settings.redis_url else None,
        )
    with _pre_ready_stage("engine", role):
        fence_engine = build_engine(settings)
    with _pre_ready_stage("database_session", role):
        connection_acquired = False
        _write_pre_ready_phase("database_connect", "entered", role)
        try:
            with fence_engine.connect() as connection:
                connection_acquired = True
                _write_pre_ready_phase("database_connect", "completed", role)
                with _pre_ready_stage("database_identity", role):
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    verify_database_connection(connection, binding)
        except Exception:
            if not connection_acquired:
                _write_pre_ready_phase("database_connect", "failed", role)
            raise
    with _pre_ready_stage("ready_publish", role):
        if role == "worker":
            install_owned_stop_watcher("worker")
        else:
            install_owned_stop_watcher("beat")

    from ai_intel.workers.runtime import celery_app, consume_job, poll_due_public_sources

    def owned_consume_job(job_id: str) -> dict[str, str]:
        require_producer_slot(fence_engine)
        require_cumulative_producer_slot(fence_engine, binding)
        return consume_job(job_id)

    def owned_poll_sources() -> dict[str, int | str]:
        require_producer_slot(fence_engine)
        require_cumulative_producer_slot(fence_engine, binding)
        return poll_due_public_sources()

    celery_app.tasks["ai_intel.jobs.execute"].run = owned_consume_job
    celery_app.tasks["ai_intel.sources.poll_due"].run = owned_poll_sources

    celery_app.conf.update(task_default_queue=QUEUE, task_default_routing_key=QUEUE)
    celery_app.conf.broker_transport_options = {
        **celery_app.conf.broker_transport_options,
        "global_keyprefix": REDIS_PREFIX,
    }
    if (
        celery_app.conf.task_default_queue != QUEUE
        or celery_app.conf.task_default_routing_key != QUEUE
        or celery_app.conf.broker_transport_options.get("global_keyprefix") != REDIS_PREFIX
    ):
        raise RuntimeError("actual Celery queue or prefix differs")
    return celery_app


if __name__ != "__main__":
    celery_app = load_owned_application()
else:
    _write_pre_ready_phase("authorization", "entered")
    from authorization import verify_live_authorization

    verify_live_authorization()
    _write_pre_ready_phase("authorization", "completed")
