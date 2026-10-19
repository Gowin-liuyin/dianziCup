"""PostgreSQL 来源游标、租约与分页回执；回调只写入当前事务。"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import JsonValue, TypeAdapter
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
)
from ai_intel.ingestion.scheduler import CursorCommitError
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    job_payloads,
    job_runs,
    outbox_events,
    source_cursors,
    source_page_receipts,
)

StreamKind = Literal["live", "backfill"]
CURSOR_ADAPTER = TypeAdapter(dict[str, JsonValue])
MAX_CURSOR_BYTES = 65536
MAX_PAGE_REQUEST_BYTES = 1048576
MAX_JSON_DEPTH = 16
MAX_JSON_NODES = 10000
MAX_PENDING_RECOVERY_JOBS = 1000


def _canonical_page_json(value: object) -> bytes:
    """只接受有界原生JSON值；不通过字符串化或类型转换丢掉请求字段。"""
    node_count = 0

    def validate(item: object, depth: int) -> None:
        nonlocal node_count
        node_count += 1
        if depth > MAX_JSON_DEPTH or node_count > MAX_JSON_NODES:
            raise ValueError("page JSON exceeds bounded depth or node count")
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) is float and isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("page JSON requires finite numbers")
            return
        if type(item) is dict and isinstance(item, dict):
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError("page JSON requires string keys")
                validate(child, depth + 1)
            return
        if type(item) is list and isinstance(item, list):
            for child in item:
                validate(child, depth + 1)
            return
        raise ValueError("page JSON contains an unsupported value")

    validate(value, 0)
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_PAGE_REQUEST_BYTES:
        raise ValueError("page JSON exceeds maximum size 1 MiB")
    return encoded


def page_request_digest(
    lease: SourceCursorLease,
    input_cursor: dict[str, JsonValue],
    output_cursor: dict[str, JsonValue],
    entries: tuple[dict[str, object], ...],
    is_last_page: bool,
    watermark_published_at: datetime | None,
) -> str:
    """服务端完整请求指纹；对象key顺序归一，条目/列表顺序与所有字段保留。"""
    if type(entries) is not tuple or any(type(entry) is not dict for entry in entries):
        raise ValueError("page entries require a tuple of JSON objects")
    if type(is_last_page) is not bool:
        raise ValueError("explicit page completion required")
    payload = {
        "fingerprint_version": "page-request-1",
        "source_id": lease.source_id,
        "stream_kind": lease.stream_kind,
        "window_start": _aware_time(lease.window_start).isoformat() if lease.window_start else None,
        "window_end": _aware_time(lease.window_end).isoformat(),
        "input_cursor": input_cursor,
        "output_cursor": output_cursor,
        "entries": list(entries),
        "is_last_page": is_last_page,
        "watermark_published_at": (
            _aware_time(watermark_published_at).isoformat() if watermark_published_at else None
        ),
    }
    return hashlib.sha256(_canonical_page_json(payload)).hexdigest()


class SourceLeaseLostError(CursorCommitError):
    """租约 owner、generation 或有效期不符，拒绝旧执行者写入。"""


class StaleSourceCursorError(CursorCommitError):
    """输入游标不是当前已提交游标，不能覆盖后续分页结果。"""


@dataclass(frozen=True)
class SourceCursorLease:
    """领取时冻结的窗口与代数；传递给连接器，不代表持久化提交成功。"""

    source_id: str
    stream_kind: StreamKind
    lease_owner: str
    generation: int
    cursor_json: dict[str, JsonValue]
    window_start: datetime | None
    window_end: datetime
    watermark_published_at: datetime | None
    last_successful_page: int
    lease_expires_at: datetime


@dataclass(frozen=True)
class PersistedPageEntry:
    """每条输入须对应同来源修订或含该条目身份的可重放任务，二选一。"""

    revision_id: str | None = None
    failed_job_id: str | None = None


@dataclass(frozen=True)
class SourcePageReceipt:
    """数据库提交回执；reused 表示读取既有页，无再次执行持久化回调。"""

    page_key: str
    input_cursor: dict[str, JsonValue]
    output_cursor: dict[str, JsonValue]
    revision_ids: tuple[str, ...]
    failed_job_ids: tuple[str, ...]
    entry_count: int
    committed_at: datetime
    reused: bool


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(UTC)


def _cursor(value: object) -> dict[str, JsonValue]:
    _canonical_page_json(value)
    validated = CURSOR_ADAPTER.validate_python(value, strict=True)
    encoded = json.dumps(validated, sort_keys=True, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_CURSOR_BYTES:
        raise ValueError("source cursor exceeds bounded size")
    return CURSOR_ADAPTER.validate_json(encoded, strict=True)


def _cursor_state(
    value: object,
) -> tuple[dict[str, JsonValue], bool, datetime | None, list[dict[str, str]] | None]:
    """旧裸游标只视为未完成；不能从空游标猜测窗口已经采集成功。"""
    _canonical_page_json(value)
    state = CURSOR_ADAPTER.validate_python(value, strict=True)
    if "window_complete" not in state:
        return _cursor(state), False, None, None
    if (
        not {"position", "window_complete"}.issubset(state)
        or set(state)
        - {
            "position",
            "window_complete",
            "pending_watermark_published_at",
            "recovery_tracking_version",
            "pending_recovery_job_ids",
        }
        or type(state["window_complete"]) is not bool
    ):
        raise CursorCommitError("invalid persisted cursor envelope")
    pending = state.get("pending_watermark_published_at")
    if pending is not None and not isinstance(pending, str):
        raise CursorCommitError("invalid pending source watermark")
    pending_time = _aware_time(datetime.fromisoformat(pending)) if pending is not None else None
    references = None
    if {"recovery_tracking_version", "pending_recovery_job_ids"} & set(state):
        if (
            type(state.get("recovery_tracking_version")) is not int
            or state.get("recovery_tracking_version") != 1
        ):
            raise CursorCommitError("invalid recovery reference tracking version")
        raw_references = state.get("pending_recovery_job_ids")
        if not isinstance(raw_references, list) or len(raw_references) > MAX_PENDING_RECOVERY_JOBS:
            raise CursorCommitError("invalid or unbounded recovery references")
        references = []
        for reference in raw_references:
            if not isinstance(reference, dict) or set(reference) != {"job_id", "entry_id"}:
                raise CursorCommitError("invalid recovery reference identity")
            references.append(
                {
                    "job_id": _identity(reference["job_id"], "job_id"),
                    "entry_id": _identity(reference["entry_id"], "entry_id"),
                }
            )
    return _cursor(state["position"]), state["window_complete"] is True, pending_time, references


def _identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(f"valid {label} required")
    return value


def _required_time(row: RowMapping, name: str) -> datetime:
    value = row[name]
    if not isinstance(value, datetime):
        raise CursorCommitError("invalid persisted cursor timestamp")
    return _aware_time(value)


def _optional_time(row: RowMapping, name: str) -> datetime | None:
    return None if row[name] is None else _required_time(row, name)


def _integer(row: RowMapping, name: str) -> int:
    value = row[name]
    if type(value) is not int or not isinstance(value, int) or value < 0:
        raise CursorCommitError("invalid persisted cursor counter")
    return value


def make_page_key(lease: SourceCursorLease, input_cursor: dict[str, JsonValue]) -> str:
    """页身份包含冻结窗口，下一轮相同源游标不会复用上一窗口的回执。"""
    identity = {
        "source_id": lease.source_id,
        "stream_kind": lease.stream_kind,
        "window_start": lease.window_start.isoformat() if lease.window_start else None,
        "window_end": lease.window_end.isoformat(),
        "input_cursor": _cursor(input_cursor),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()


class SourceCursorRepository:
    """绑定受信来源配置和认证范围；事务由调用方提交，分页失败仅撤销整页。"""

    def __init__(
        self,
        session: Session,
        scope: AccessScope,
        source_id: str,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.session = session
        self.scope = scope
        self.source_id = _identity(source_id, "source_id")
        self.clock = clock

    def _source_scope(self) -> tuple[str, str | None]:
        source = (
            self.session.execute(
                text("SELECT visibility, tenant_id FROM sources WHERE source_id=:source_id"),
                {"source_id": self.source_id},
            )
            .mappings()
            .first()
        )
        if source is None:
            raise CrossTenantAccessError("resource not found")
        visibility = source["visibility"]
        tenant_id = source["tenant_id"]
        if visibility not in {"public", "tenant"} or (
            (visibility == "public" and tenant_id is not None)
            or (visibility == "tenant" and (not isinstance(tenant_id, str) or not tenant_id))
        ):
            raise CursorCommitError("invalid configured source scope")
        self.scope.enforce_visible(visibility, tenant_id)
        self.scope.requires(MANAGE_PUBLIC_SOURCES if visibility == "public" else WRITE_ASSET)
        return visibility, tenant_id

    def _key_conditions(self, stream_kind: StreamKind) -> tuple[ColumnElement[bool], ...]:
        return (
            source_cursors.c.source_id == self.source_id,
            source_cursors.c.stream_kind == stream_kind,
        )

    def _lease_from_row(self, row: RowMapping) -> SourceCursorLease:
        stream_kind = row["stream_kind"]
        if stream_kind not in ("live", "backfill"):
            raise CursorCommitError("invalid persisted stream kind")
        return SourceCursorLease(
            source_id=self.source_id,
            stream_kind=stream_kind,
            lease_owner=_identity(row["lease_owner"], "lease_owner"),
            generation=_integer(row, "generation"),
            cursor_json=_cursor_state(row["cursor_json"])[0],
            window_start=_optional_time(row, "window_start"),
            window_end=_required_time(row, "window_end"),
            watermark_published_at=_optional_time(row, "watermark_published_at"),
            last_successful_page=_integer(row, "last_successful_page"),
            lease_expires_at=_required_time(row, "lease_expires_at"),
        )

    def claim(
        self,
        *,
        stream_kind: StreamKind,
        lease_owner: str,
        window_start: datetime | None,
        window_end: datetime,
        lease_seconds: int = 60,
    ) -> SourceCursorLease | None:
        """只领取无有效租约的流；未完成窗口接管时保留原窗口和分页位置。"""
        if stream_kind not in ("live", "backfill"):
            raise ValueError("unsupported source stream")
        lease_owner = _identity(lease_owner, "lease_owner")
        expires_delta = self._lease_delta(lease_seconds)
        now = _aware_time(self.clock())
        window_end = _aware_time(window_end)
        window_start = _aware_time(window_start) if window_start is not None else None
        if window_end > now or (window_start is not None and window_start > window_end):
            raise ValueError("source window must be ordered and end no later than current time")
        with self.session.begin_nested():
            self._source_scope()
            self.session.execute(
                insert(source_cursors)
                .values(
                    source_id=self.source_id,
                    stream_kind=stream_kind,
                    cursor_json={},
                    last_successful_page=0,
                    generation=0,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["source_id", "stream_kind"])
            )
            row = (
                self.session.execute(
                    select(source_cursors)
                    .where(*self._key_conditions(stream_kind))
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            now = _aware_time(self.clock())
            expiry = _optional_time(row, "lease_expires_at")
            if expiry is not None and expiry > now:
                return None
            unfinished_window = _optional_time(row, "window_end")
            position, window_complete, _, _ = _cursor_state(row["cursor_json"])
            values: dict[str, object] = {
                "lease_owner": lease_owner,
                "lease_expires_at": now + expires_delta,
                "generation": _integer(row, "generation") + 1,
                "updated_at": now,
            }
            if unfinished_window is None or window_complete:
                values.update(
                    window_start=window_start,
                    window_end=window_end,
                    last_successful_page=0,
                    cursor_json={
                        "position": position,
                        "window_complete": False,
                        "pending_watermark_published_at": None,
                        "recovery_tracking_version": 1,
                        "pending_recovery_job_ids": [],
                    },
                )
            claimed = (
                self.session.execute(
                    update(source_cursors)
                    .where(*self._key_conditions(stream_kind))
                    .values(**values)
                    .returning(source_cursors)
                )
                .mappings()
                .one()
            )
            return self._lease_from_row(claimed)

    @staticmethod
    def _lease_delta(lease_seconds: int) -> timedelta:
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("source lease must be bounded to 1..3600 seconds")
        return timedelta(seconds=lease_seconds)

    def _lock_lease(self, lease: SourceCursorLease) -> RowMapping:
        if lease.source_id != self.source_id or lease.stream_kind not in ("live", "backfill"):
            raise SourceLeaseLostError("source lease no longer valid")
        row = (
            self.session.execute(
                select(source_cursors)
                .where(*self._key_conditions(lease.stream_kind))
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise SourceLeaseLostError("source lease no longer valid")
        self._verify_lease(row, lease)
        return row

    def _verify_lease(self, row: RowMapping, lease: SourceCursorLease) -> None:
        expiry = _optional_time(row, "lease_expires_at")
        if (
            row["lease_owner"] != lease.lease_owner
            or row["generation"] != lease.generation
            or expiry is None
            or expiry <= _aware_time(self.clock())
            or _optional_time(row, "window_start") != lease.window_start
            or _optional_time(row, "window_end") != lease.window_end
        ):
            raise SourceLeaseLostError("source lease no longer valid")

    def _active_lease_conditions(
        self, lease: SourceCursorLease, now: datetime
    ) -> tuple[ColumnElement[bool], ...]:
        return (
            *self._key_conditions(lease.stream_kind),
            source_cursors.c.lease_owner == lease.lease_owner,
            source_cursors.c.generation == lease.generation,
            source_cursors.c.lease_expires_at > now,
        )

    def renew(self, lease: SourceCursorLease, *, lease_seconds: int = 60) -> SourceCursorLease:
        """续期只延长当前有效代数；相同 owner 的旧代数同样拒绝。"""
        delta = self._lease_delta(lease_seconds)
        with self.session.begin_nested():
            self._source_scope()
            self._lock_lease(lease)
            now = _aware_time(self.clock())
            renewed = (
                self.session.execute(
                    update(source_cursors)
                    .where(*self._active_lease_conditions(lease, now))
                    .values(lease_expires_at=now + delta, updated_at=now)
                    .returning(source_cursors)
                )
                .mappings()
                .first()
            )
            if renewed is None:
                raise SourceLeaseLostError("source lease no longer valid")
            return self._lease_from_row(renewed)

    def release(self, lease: SourceCursorLease) -> None:
        """主动让出未完成窗口，后续领取保留分页位置与冻结的查询范围。"""
        with self.session.begin_nested():
            self._source_scope()
            self._lock_lease(lease)
            now = _aware_time(self.clock())
            released = self.session.execute(
                update(source_cursors)
                .where(*self._active_lease_conditions(lease, now))
                .values(lease_owner=None, lease_expires_at=None, updated_at=now)
                .returning(source_cursors.c.source_id)
            ).first()
            if released is None:
                raise SourceLeaseLostError("source lease no longer valid")

    def _validate_entry(
        self, entry: dict[str, object], visibility: str, tenant_id: str | None
    ) -> str:
        entry_id = _identity(entry.get("entry_id"), "entry_id")
        for name, expected in (
            ("source_id", self.source_id),
            ("visibility", visibility),
            ("tenant_id", tenant_id),
        ):
            if name in entry and entry[name] != expected:
                raise CursorCommitError("entry conflicts with configured source scope")
        return entry_id

    def _verify_persisted_entry(
        self, saved: PersistedPageEntry, entry_id: str, visibility: str, tenant_id: str | None
    ) -> None:
        if not isinstance(saved, PersistedPageEntry) or bool(saved.revision_id) == bool(
            saved.failed_job_id
        ):
            raise CursorCommitError("each entry requires one durable revision or recovery job")
        if saved.revision_id is not None:
            _identity(saved.revision_id, "revision_id")
            row = (
                self.session.execute(
                    select(document_revisions.c.visibility, document_revisions.c.tenant_id)
                    .join(documents, documents.c.document_id == document_revisions.c.document_id)
                    .where(
                        document_revisions.c.revision_id == saved.revision_id,
                        documents.c.source_id == self.source_id,
                        documents.c.visibility == visibility,
                        documents.c.tenant_id.is_(None)
                        if tenant_id is None
                        else documents.c.tenant_id == tenant_id,
                    )
                )
                .mappings()
                .first()
            )
            if row is None or row["visibility"] != visibility or row["tenant_id"] != tenant_id:
                raise CursorCommitError("revision does not belong to configured source scope")
            return
        job_id = _identity(saved.failed_job_id, "failed_job_id")
        job = (
            self.session.execute(
                select(job_runs, job_payloads.c.payload)
                .join(job_payloads, job_payloads.c.job_id == job_runs.c.job_id)
                .where(job_runs.c.job_id == job_id)
                .with_for_update(of=job_runs)
            )
            .mappings()
            .first()
        )
        if (
            job is None
            or job["tenant_id"] != tenant_id
            or job["status"] not in {"queued", "retry_wait", "running"}
            or not 0 <= _integer(job, "attempt_count") < _integer(job, "max_attempts") <= 10
        ):
            raise CursorCommitError("recovery job unavailable in configured source scope")
        if job["status"] == "retry_wait" and _optional_time(job, "next_retry_at") is None:
            raise CursorCommitError("recovery job has no durable retry schedule")
        if job["status"] == "running" and (
            not job["lease_owner"] or _optional_time(job, "lease_expires_at") is None
        ):
            raise CursorCommitError("recovery job has no recoverable lease")
        payload = job["payload"]
        if (
            not isinstance(payload, bytes)
            or job["payload_ref"] != f"pg:job:{job_id}"
            or hashlib.sha256(payload).hexdigest() != job["payload_sha256"]
        ):
            raise CursorCommitError("recovery job payload is not durable")
        delivery = self.session.execute(
            select(outbox_events.c.event_id)
            .where(
                outbox_events.c.job_id == job_id,
                outbox_events.c.payload_ref == job["payload_ref"],
            )
            .limit(1)
        ).first()
        if delivery is None:
            raise CursorCommitError("recovery job has no durable delivery")
        try:
            identity = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise CursorCommitError("recovery job has no replayable entry identity") from None
        if not isinstance(identity, dict) or (
            identity.get("source_id") != self.source_id or identity.get("entry_id") != entry_id
        ):
            raise CursorCommitError("recovery job has no replayable entry identity")

    def commit_page(
        self,
        lease: SourceCursorLease,
        *,
        page_key: str,
        input_cursor: dict[str, JsonValue],
        output_cursor: dict[str, JsonValue],
        entries: tuple[dict[str, object], ...],
        persist_entry: Callable[[Session, dict[str, object]], PersistedPageEntry],
        is_last_page: bool,
        watermark_published_at: datetime | None = None,
    ) -> SourcePageReceipt:
        """整页事实/失败任务、回执和游标原子写入；回调不得提交或关闭 Session。"""
        input_cursor, output_cursor = _cursor(input_cursor), _cursor(output_cursor)
        if page_key != make_page_key(lease, input_cursor):
            raise ValueError("page_key must identify the frozen source window and input cursor")
        if type(is_last_page) is not bool:
            raise ValueError("explicit page completion required")
        if watermark_published_at is not None:
            watermark_published_at = _aware_time(watermark_published_at)
            if watermark_published_at > lease.window_end:
                raise ValueError("watermark exceeds frozen source window")
        request_sha256 = page_request_digest(
            lease,
            input_cursor,
            output_cursor,
            entries,
            is_last_page,
            watermark_published_at,
        )
        with self.session.begin_nested():
            visibility, tenant_id = self._source_scope()
            row = self._lock_lease(lease)
            entry_ids = [self._validate_entry(entry, visibility, tenant_id) for entry in entries]
            existing = (
                self.session.execute(
                    select(source_page_receipts).where(
                        source_page_receipts.c.source_id == self.source_id,
                        source_page_receipts.c.stream_kind == lease.stream_kind,
                        source_page_receipts.c.page_key == page_key,
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None:
                if existing["request_sha256"] is None:
                    raise CursorCommitError("legacy_page_receipt_unverifiable")
                if existing["request_sha256"] != request_sha256:
                    raise CursorCommitError("page receipt conflicts with replay")
                return self._receipt(existing, reused=True)
            current_cursor, window_complete, pending_watermark, pending_recovery = _cursor_state(
                row["cursor_json"]
            )
            if window_complete or current_cursor != input_cursor:
                raise StaleSourceCursorError("input cursor no longer current")
            if pending_recovery is None:
                raise CursorCommitError("legacy_window_recovery_unverifiable")
            if pending_watermark is not None and pending_watermark > lease.window_end:
                raise CursorCommitError("pending watermark exceeds frozen source window")
            revision_ids: list[str] = []
            failed_job_ids: list[str] = []
            persisted_entries: list[tuple[PersistedPageEntry, str]] = []
            for entry, entry_id in zip(entries, entry_ids, strict=True):
                saved = persist_entry(self.session, entry)
                self._verify_persisted_entry(saved, entry_id, visibility, tenant_id)
                persisted_entries.append((saved, entry_id))
                if saved.revision_id is not None:
                    revision_ids.append(saved.revision_id)
                elif saved.failed_job_id is not None:
                    failed_job_ids.append(saved.failed_job_id)
                    reference = {"job_id": saved.failed_job_id, "entry_id": entry_id}
                    if reference not in pending_recovery:
                        pending_recovery.append(reference)
                        if len(pending_recovery) > MAX_PENDING_RECOVERY_JOBS:
                            raise CursorCommitError(
                                "window recovery references exceed bounded limit"
                            )
            for saved, entry_id in persisted_entries:
                self._verify_persisted_entry(saved, entry_id, visibility, tenant_id)
            if is_last_page:
                for reference in pending_recovery:
                    self._verify_persisted_entry(
                        PersistedPageEntry(failed_job_id=reference["job_id"]),
                        reference["entry_id"],
                        visibility,
                        tenant_id,
                    )
            self._verify_lease(row, lease)
            now = _aware_time(self.clock())
            if lease.stream_kind == "live" and watermark_published_at is not None:
                pending_watermark = max(
                    watermark_published_at, pending_watermark or watermark_published_at
                )
            values: dict[str, object] = {
                "cursor_json": {
                    "position": output_cursor,
                    "window_complete": is_last_page,
                    "pending_watermark_published_at": (
                        pending_watermark.isoformat()
                        if pending_watermark is not None and not is_last_page
                        else None
                    ),
                    "recovery_tracking_version": 1,
                    "pending_recovery_job_ids": [] if is_last_page else pending_recovery,
                },
                "last_successful_page": _integer(row, "last_successful_page") + 1,
                "updated_at": now,
            }
            current_watermark = _optional_time(row, "watermark_published_at")
            try:
                _canonical_page_json(values["cursor_json"])
            except ValueError:
                raise CursorCommitError("window recovery references exceed bounded JSON") from None
            if lease.stream_kind == "live" and is_last_page and pending_watermark is not None:
                values["watermark_published_at"] = max(
                    pending_watermark, current_watermark or pending_watermark
                )
            updated = self.session.execute(
                update(source_cursors)
                .where(*self._active_lease_conditions(lease, now))
                .values(**values)
                .returning(source_cursors.c.source_id)
            ).first()
            if updated is None:
                raise SourceLeaseLostError("source lease no longer valid")
            receipt = (
                self.session.execute(
                    source_page_receipts.insert()
                    .values(
                        source_id=self.source_id,
                        stream_kind=lease.stream_kind,
                        page_key=page_key,
                        input_cursor=input_cursor,
                        output_cursor=output_cursor,
                        revision_ids=revision_ids,
                        failed_job_ids=failed_job_ids,
                        entry_count=len(entries),
                        request_sha256=request_sha256,
                        committed_at=now,
                    )
                    .returning(source_page_receipts)
                )
                .mappings()
                .one()
            )
            return self._receipt(receipt, reused=False)

    @staticmethod
    def _receipt(row: RowMapping, *, reused: bool) -> SourcePageReceipt:
        revision_ids, failed_job_ids = row["revision_ids"], row["failed_job_ids"]
        if not isinstance(revision_ids, list) or not isinstance(failed_job_ids, list):
            raise CursorCommitError("invalid persisted page references")
        return SourcePageReceipt(
            page_key=_identity(row["page_key"], "page_key"),
            input_cursor=_cursor(row["input_cursor"]),
            output_cursor=_cursor(row["output_cursor"]),
            revision_ids=tuple(_identity(value, "revision_id") for value in revision_ids),
            failed_job_ids=tuple(_identity(value, "failed_job_id") for value in failed_job_ids),
            entry_count=_integer(row, "entry_count"),
            committed_at=_required_time(row, "committed_at"),
            reused=reused,
        )
