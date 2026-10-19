"""Arrange bounded fixed-source rounds in the existing PG job/outbox transaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    AccessScope,
    PermissionDeniedError,
    Role,
)
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES, SourceKind
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.ingestion.source_jobs import (
    SOURCE_JOB_TYPE,
    SourcePageRequest,
    enqueue_source_page,
)
from ai_intel.knowledge.models import job_payloads, job_runs

SOURCE_POLL_INTERVAL_SECONDS: dict[SourceKind, int] = {
    "nvd_ollama": 3600,
    "vllm_vendor": 1800,
    "osv_ollama": 3600,
    "avid_community": 3600,
    "ollama_releases": 3600,
    "trailofbits_blog": 3600,
    "arxiv_security": 3600,
    "nist_ai_rmf": 3600,
    "cac_generative_ai": 3600,
}
SOURCE_POLL_PAGE_LIMIT = 5
ACTIVE_SOURCE_STATUSES = ("queued", "running", "retry_wait", "waiting_approval")
MAX_ACTIVE_SOURCE_JOBS = 500
MAX_SOURCE_REQUEST_BYTES = 4096


class SourcePollingError(RuntimeError):
    """An invalid or overfull durable source queue must not create more work."""


@dataclass(frozen=True)
class PollDispatchResult:
    queued_job_ids: tuple[str, ...]
    already_scheduled: int
    busy_sources: tuple[SourceKind, ...]


def source_poll_window(source_kind: SourceKind, observed_at: datetime) -> datetime:
    """Pin each source's request to the same UTC bucket across tick/restart retries."""
    if source_kind not in SOURCE_POLL_INTERVAL_SECONDS or observed_at.utcoffset() is None:
        raise ValueError("registered source and aware polling time required")
    interval = SOURCE_POLL_INTERVAL_SECONDS[source_kind]
    return datetime.fromtimestamp((observed_at.timestamp() // interval) * interval, UTC)


def _active_sources(session: Session) -> set[SourceKind]:
    query = (
        select(
            case(
                (
                    func.octet_length(job_payloads.c.payload) <= MAX_SOURCE_REQUEST_BYTES,
                    job_payloads.c.payload,
                ),
                else_=b"",
            ).label("payload")
        )
        .select_from(job_runs.outerjoin(job_payloads, job_payloads.c.job_id == job_runs.c.job_id))
        .where(
            job_runs.c.tenant_id.is_(None),
            job_runs.c.job_type == SOURCE_JOB_TYPE,
            job_runs.c.status.in_(ACTIVE_SOURCE_STATUSES),
        )
        .limit(MAX_ACTIVE_SOURCE_JOBS + 1)
    )
    rows = session.execute(query).mappings().all()
    if len(rows) > MAX_ACTIVE_SOURCE_JOBS:
        raise SourcePollingError("public source queue exceeds polling limit")
    active: set[SourceKind] = set()
    for row in rows:
        payload = row["payload"]
        if not isinstance(payload, bytes):
            raise SourcePollingError("active source request is unavailable")
        try:
            active.add(SourcePageRequest.model_validate_json(payload).source_kind)
        except ValidationError:
            raise SourcePollingError("active source request is invalid") from None
    return active


def enqueue_due_source_collections(
    session: Session, access_scope: AccessScope, observed_at: datetime
) -> PollDispatchResult:
    """The caller commits once; no network IO or second scheduling state is introduced."""
    access_scope.requires(MANAGE_PUBLIC_SOURCES)
    if access_scope.role != Role.SYSTEM_ADMIN or access_scope.tenant_id is not None:
        raise PermissionDeniedError("public source administrator required")
    if observed_at.utcoffset() is None:
        raise ValueError("aware polling time required")
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended("source-poll-v1", 0))))
    active = _active_sources(session)
    queued = []
    already_scheduled = 0
    busy = []
    for source_kind in CATALOG_SOURCES:
        if source_kind in active:
            busy.append(source_kind)
            continue
        window = source_poll_window(source_kind, observed_at)
        key = f"source-poll-v1:{source_kind}:{int(window.timestamp())}"
        existing = session.scalar(
            select(job_runs.c.job_id).where(
                job_runs.c.tenant_id.is_(None),
                job_runs.c.job_type == SOURCE_JOB_TYPE,
                job_runs.c.idempotency_key == key,
            )
        )
        if existing is not None:
            already_scheduled += 1
            continue
        ensure_source_registration(session, access_scope, source_kind, observed_at)
        queued.append(
            enqueue_source_page(
                session,
                SourcePageRequest(
                    source_kind=source_kind,
                    stream_kind="live",
                    window_end=window,
                    remaining_pages=SOURCE_POLL_PAGE_LIMIT,
                ),
                observed_at,
                idempotency_key=key,
            )
        )
    return PollDispatchResult(tuple(queued), already_scheduled, tuple(busy))
