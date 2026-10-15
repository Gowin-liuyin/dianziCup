"""Commit bounded source response evidence independently of parsing and cursor effects."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue
from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.domain.access import MANAGE_PUBLIC_SOURCES, READ_PUBLIC, AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.minio_store import ObjectStoreUnavailableError
from ai_intel.infrastructure.network import MAX_RESPONSE_BYTES, FetchResult
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES, CatalogRequest, SourceKind
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.knowledge.models import job_runs
from ai_intel.knowledge.revisions import register_response_content
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError
from ai_intel.workers.jobs import read_job_payload

RECEIPT_ERROR_CODES = frozenset(
    {
        "source_response_invalid",
        "source_network_policy_denied",
        "network_error",
        "network_dns_error",
        "network_tls_error",
        "network_timeout",
        "response_too_large",
        "unsupported_content_type",
        "source_auth_denied",
        "source_rate_limited",
        "source_client_error",
        "source_server_error",
        "source_unexpected_status",
        "source_response_storage_failed",
        "database_operation_failed",
        "handler_failed",
    }
)
RECEIPT_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "application/rss+xml",
        "application/atom+xml",
        "application/xml",
        "text/xml",
        "application/pdf",
        "text/html",
    }
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SourceResponseRecorder:
    """Trusted handler context; receipt references must survive its outer transaction rollback."""

    engine: Engine
    store: ContentStorage
    scope: AccessScope
    context: JobExecutionContext
    source_kind: SourceKind
    stream_kind: Literal["live", "backfill"]
    window_end: datetime
    input_cursor: dict[str, JsonValue]

    def _validate_context(self, session: Session, observed_at: datetime) -> None:
        self.scope.requires(MANAGE_PUBLIC_SOURCES)
        self.scope.requires(READ_PUBLIC)
        if (
            self.scope.role != Role.SYSTEM_ADMIN
            or self.scope.tenant_id is not None
            or self.context.tenant_id is not None
        ):
            raise JobExecutionError("source_scope_denied", blocked=True)
        if (
            observed_at.utcoffset() is None
            or self.window_end.utcoffset() is None
            or self.window_end > observed_at
        ):
            raise JobExecutionError("source_receipt_context_invalid", blocked=True)
        row = (
            session.execute(select(job_runs).where(job_runs.c.job_id == self.context.job_id))
            .mappings()
            .first()
        )
        if row is None or (
            row["tenant_id"] is not None
            or row["job_type"] != "collect_public_source_page"
            or row["status"] != "running"
            or row["lease_owner"] != self.context.worker_id
            or row["attempt_count"] != self.context.attempt_count
            or row["lease_expires_at"] <= observed_at
        ):
            raise JobExecutionError("source_receipt_context_invalid", blocked=True)
        payload = json.loads(read_job_payload(session, self.context.job_id, None))
        if not isinstance(payload, dict) or (
            payload.get("source_kind") != self.source_kind
            or payload.get("stream_kind") != self.stream_kind
        ):
            raise JobExecutionError("source_receipt_context_invalid", blocked=True)
        requested_window = payload.get("window_end")
        if (
            not isinstance(requested_window, str)
            or datetime.fromisoformat(requested_window) < self.window_end
        ):
            raise JobExecutionError("source_receipt_context_invalid", blocked=True)

    def record_response(
        self,
        request: CatalogRequest,
        response: FetchResult | None,
        ordinal: int,
        observed_at: datetime,
        *,
        allowed_content_types: tuple[str, ...],
    ) -> str:
        """Only validated HTTP200 bytes are retained; transport metadata never invents a body."""
        if (
            type(ordinal) is not int
            or not 1 <= ordinal <= 2
            or self.source_kind not in CATALOG_SOURCES
        ):
            raise JobExecutionError("source_receipt_context_invalid", blocked=True)
        status, media = None, None
        body: bytes | None = None
        if response is not None:
            if type(response.status_code) is not int or not 100 <= response.status_code <= 599:
                raise JobExecutionError("source_response_invalid", blocked=True)
            status = response.status_code
            candidate_media = response.content_type.split(";", 1)[0].strip().casefold()
            media = candidate_media if candidate_media in RECEIPT_CONTENT_TYPES else None
            if status == 200 and media in allowed_content_types:
                if type(response.body) is not bytes or len(response.body) > MAX_RESPONSE_BYTES:
                    raise JobExecutionError("response_too_large", blocked=True)
                body = response.body
        receipt_id = str(
            uuid5(
                NAMESPACE_URL,
                f"dianzi:source-response:{self.context.job_id}:{self.context.attempt_count}:{ordinal}",
            )
        )
        values: dict[str, object] = {
            "receipt_id": receipt_id,
            "schema_version": 1,
            "job_id": self.context.job_id,
            "attempt_count": self.context.attempt_count,
            "response_ordinal": ordinal,
            "source_kind": self.source_kind,
            "source_id": CATALOG_SOURCES[self.source_kind].source_id,
            "stream_kind": self.stream_kind,
            "window_end": self.window_end,
            "input_cursor_sha256": _digest(self.input_cursor),
            "request_fingerprint_sha256": _digest([request.method, request.url, request.json_body]),
            "observed_at": observed_at,
            "http_status": status,
            "content_type": media,
            "response_content_hash": None,
            "response_size_bytes": None,
            "parse_outcome": "received",
            "error_code": None,
        }
        storage_failed = False
        try:
            with Session(self.engine) as session, session.begin():
                self._validate_context(session, observed_at)
                if body is not None:
                    try:
                        with session.begin_nested():
                            stored = register_response_content(
                                session, self.store, body, observed_at
                            )
                            values.update(
                                response_content_hash=stored.content_hash,
                                response_size_bytes=stored.size_bytes,
                            )
                    except (OSError, ValueError, ObjectStoreUnavailableError):
                        storage_failed = True
                        values.update(
                            parse_outcome="transport_failed",
                            error_code="source_response_storage_failed",
                        )
                session.execute(
                    insert(source_response_receipts)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=[source_response_receipts.c.receipt_id])
                )
                prior = (
                    session.execute(
                        select(source_response_receipts).where(
                            source_response_receipts.c.receipt_id == receipt_id
                        )
                    )
                    .mappings()
                    .one()
                )
                immutable_fields = set(values) - {"observed_at", "parse_outcome", "error_code"}
                if any(prior[name] != values[name] for name in immutable_fields):
                    raise JobExecutionError("source_receipt_replay_conflict", blocked=True)
        except SQLAlchemyError:
            raise JobExecutionError(
                "source_receipt_database_failed", retry_after_seconds=7
            ) from None
        except JobExecutionError:
            raise
        if storage_failed:
            raise JobExecutionError("source_response_storage_failed", retry_after_seconds=7)
        return receipt_id

    def mark_outcome(
        self,
        outcome: Literal["normalized", "normalization_failed", "transport_failed"],
        observed_at: datetime,
        *,
        error_code: str | None = None,
        ordinal: int | None = None,
    ) -> None:
        """A parse marker describes response handling, never job completion or live coverage."""
        if error_code is not None and error_code not in RECEIPT_ERROR_CODES:
            raise JobExecutionError("source_receipt_context_invalid", blocked=True)
        try:
            with Session(self.engine) as session, session.begin():
                self._validate_context(session, observed_at)
                statement = update(source_response_receipts).where(
                    source_response_receipts.c.job_id == self.context.job_id,
                    source_response_receipts.c.attempt_count == self.context.attempt_count,
                    source_response_receipts.c.parse_outcome == "received",
                )
                if ordinal is not None:
                    statement = statement.where(
                        source_response_receipts.c.response_ordinal == ordinal
                    )
                recorded_outcome = (
                    case(
                        (source_response_receipts.c.response_content_hash.is_not(None), "received"),
                        else_="transport_failed",
                    )
                    if outcome == "transport_failed"
                    else outcome
                )
                session.execute(
                    statement.values(parse_outcome=recorded_outcome, error_code=error_code)
                )
        except SQLAlchemyError:
            raise JobExecutionError(
                "source_receipt_database_failed", retry_after_seconds=7
            ) from None
