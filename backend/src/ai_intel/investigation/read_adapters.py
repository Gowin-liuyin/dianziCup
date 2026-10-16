"""Three bounded internal reads reuse the authoritative PostgreSQL business services."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import get_ident
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from sqlalchemy import case, event, func, select, tuple_
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.engine import Connection, ExecutionContext, RowMapping
from sqlalchemy.engine.interfaces import DBAPICursor
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import Principal
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.api.knowledge_read_service import (
    EventFilters,
    InvalidEventCursor,
    KnowledgeReadService,
    decode_event_cursor,
    encode_event_cursor,
    sources,
)
from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.domain.access import (
    READ_ASSET,
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.domain.enums import ToolStatus
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.investigation.tool_contracts import (
    ChangesPage,
    ChangeSummary,
    FindChangesArguments,
    FindChangesCall,
    GetAdvisoryArguments,
    GetAdvisoryCall,
    GetInventoryArguments,
    GetInventoryCall,
    SharedReadCall,
    SharedReadData,
    ToolName,
)
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService, GraphReadInputs
from ai_intel.knowledge.models import document_revisions, documents, evidence, scope_epochs
from ai_intel.knowledge.persistence_models import (
    change_events,
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)

if TYPE_CHECKING:
    from ai_intel.api.actor_references import ActorReference

MAX_PARENT_ROWS = 256
MAX_CHANGE_CANDIDATES = 100
READ_TOOLS = frozenset({ToolName.GET_ADVISORY, ToolName.GET_INVENTORY, ToolName.FIND_CHANGES})


class ReadAdapterUnavailableError(RuntimeError):
    """No safe caller-owned connected executor is available; no fallback is permitted."""


class ReadSnapshotChangedError(RuntimeError):
    """Current authenticated inputs or an opaque continuation changed before return."""


class ReadCandidateLimitError(RuntimeError):
    """The fixed parent scan bound cannot prove this read complete."""


@dataclass(frozen=True)
class ReadToolOutcome:
    data: SharedReadData | None
    status: ToolStatus
    error_code: str | None
    observed_at: datetime | None
    limitations: tuple[str, ...]


class ReadToolAdapter(Protocol):
    @property
    def data_mode(self) -> DataMode: ...

    @property
    def configured_tools(self) -> frozenset[ToolName]: ...

    def read_tool(
        self,
        principal: Principal,
        scope: AccessScope,
        call: SharedReadCall,
        deadline_monotonic: float,
    ) -> ReadToolOutcome: ...


@dataclass(frozen=True)
class _EventInputs:
    graph: GraphReadInputs
    fingerprint: str
    all_visible: bool
    result_ids: tuple[str, ...]
    external_ids: tuple[tuple[str, str], ...]


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _bounded_rows(session: Session, query: Select) -> list[RowMapping]:
    rows = list(session.execute(query.limit(MAX_PARENT_ROWS + 1)).mappings())
    if len(rows) > MAX_PARENT_ROWS:
        raise ReadCandidateLimitError("parent read exceeds fixed bound")
    return rows


class PostgresReadToolAdapter:
    """Uses one preconnected caller-owned connection, with the existing fresh-auth fences.

    Acquisition is outside this adapter and remains in the caller's overall deadline.
    Only SELECT statements and existing FOR SHARE validity locks are permitted. Nothing
    here calls a model, fetches URLs, scans network assets or writes business facts.
    """

    def __init__(
        self, connection: Connection, actor: str | ActorReference, data_mode: DataMode
    ) -> None:
        if (
            connection.dialect.name != "postgresql"
            or not actor
            or data_mode not in {"live", "fixture"}
        ):
            raise ValueError("authenticated connected PostgreSQL and explicit mode required")
        self._connection = connection
        self._actor = actor
        self._data_mode = data_mode
        self._owner_thread = get_ident()

    @property
    def data_mode(self) -> DataMode:
        return self._data_mode

    @property
    def configured_tools(self) -> frozenset[ToolName]:
        return READ_TOOLS

    @staticmethod
    def _read_epochs(
        session: Session, scope: AccessScope, *, lock: bool = False
    ) -> tuple[tuple[str, int], ...]:
        """Asset-only credentials read their tenant epoch without acquiring public permission."""
        if READ_PUBLIC in scope.permissions:
            return EvidenceGraphReadService(session, scope).read_scope_epochs(lock=lock)
        scope.requires(READ_ASSET)
        if scope.tenant_id is None:
            raise PermissionDeniedError("tenant asset scope required")
        query = (
            select(scope_epochs.c.scope_key, scope_epochs.c.epoch)
            .where(scope_epochs.c.scope_key == "tenant:" + scope.tenant_id)
            .limit(1)
        )
        if lock:
            query = query.with_for_update(read=True)
        return tuple((row.scope_key, row.epoch) for row in session.execute(query))

    @contextmanager
    def _authenticated_read(
        self,
        principal: Principal,
        scope: AccessScope,
        permission: str,
        deadline: float,
    ) -> Iterator[tuple[Session, AccessScope]]:
        connection = self._connection
        if (
            get_ident() != self._owner_thread
            or connection.closed
            or connection.invalidated
            or connection.in_transaction()
        ):
            raise ReadAdapterUnavailableError("connected executor unavailable")

        def bound_statement(
            connection: Connection,
            cursor: DBAPICursor,
            statement: str,
            parameters: object,
            context: ExecutionContext,
            executemany: bool,
        ) -> None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("tool deadline exhausted")
            milliseconds = max(1, math.floor(remaining * 1000))
            cursor.execute(f"SET LOCAL statement_timeout = '{milliseconds}ms'")
            cursor.execute(f"SET LOCAL lock_timeout = '{milliseconds}ms'")
            if not statement.lstrip().upper().startswith("SELECT"):
                raise ReadAdapterUnavailableError("read executor received a non-read statement")

        event.listen(connection, "before_cursor_execute", bound_statement)
        try:
            connection.execution_options(isolation_level="READ COMMITTED")
            with connection.begin(), Session(bind=connection) as session:
                expected = AccessScope.for_authenticated_user(
                    principal.user_id, principal.tenant_id, principal.role
                )
                authenticated = lock_authenticated_scope(connection, self._actor, datetime.now(UTC))
                expected_identity = (
                    expected.user_id,
                    expected.tenant_id,
                    expected.role,
                    expected.permission_version,
                )
                authenticated_identity = (
                    authenticated.user_id,
                    authenticated.tenant_id,
                    authenticated.role,
                    authenticated.permission_version,
                )
                scoped_identity = (scope.user_id, scope.role, scope.permission_version)
                if (
                    authenticated_identity != expected_identity
                    or scope.tenant_id not in {None, expected.tenant_id}
                    or scoped_identity
                    != (expected.user_id, expected.role, expected.permission_version)
                ):
                    raise PermissionDeniedError("authenticated scope changed")
                effective = replace(
                    scope, permissions=scope.permissions & authenticated.permissions
                )
                effective.requires(permission)
                epochs = self._read_epochs(session, effective)
                yield session, effective
                if self._read_epochs(session, effective, lock=True) != epochs:
                    raise ReadSnapshotChangedError("scope epochs changed")
                if (
                    lock_authenticated_scope(connection, self._actor, datetime.now(UTC))
                    != authenticated
                ):
                    raise PermissionDeniedError("authenticated scope changed")
                if time.monotonic() >= deadline:
                    raise TimeoutError("tool deadline exhausted")
        finally:
            event.remove(connection, "before_cursor_execute", bound_statement)

    def _event_inputs(self, reader: KnowledgeReadService, event_id: UUID) -> _EventInputs:
        session = reader.session
        event_row = (
            session.execute(
                select(events)
                .where(events.c.event_id == str(event_id), reader._visible(events))
                .limit(1)
            )
            .mappings()
            .first()
        )
        if event_row is None:
            raise CrossTenantAccessError("resource not found")
        parent_rows = _bounded_rows(
            session,
            select(
                document_revisions.c.revision_id,
                document_revisions.c.document_id,
                document_revisions.c.is_current,
                documents.c.source_id,
                document_revisions.c.visibility.label("revision_visibility"),
                document_revisions.c.tenant_id.label("revision_tenant"),
                documents.c.visibility.label("document_visibility"),
                documents.c.tenant_id.label("document_tenant"),
                sources.c.visibility.label("source_visibility"),
                sources.c.tenant_id.label("source_tenant"),
                reader._revision_visible().label("visible"),
                event_documents.c.active,
            )
            .select_from(
                event_documents.join(
                    reader._revision_join(),
                    event_documents.c.revision_id == document_revisions.c.revision_id,
                )
            )
            .where(event_documents.c.event_id == str(event_id))
            .order_by(document_revisions.c.revision_id),
        )
        revision_ids = tuple(row["revision_id"] for row in parent_rows)
        claim_rows = _bounded_rows(
            session,
            select(claims, reader._visible(claims).label("visible"))
            .where(claims.c.source_revision_id.in_(revision_ids))
            .order_by(claims.c.claim_id),
        )
        claim_ids = tuple(row["claim_id"] for row in claim_rows)
        evidence_rows = _bounded_rows(
            session,
            select(evidence, reader._visible(evidence).label("visible"))
            .where(evidence.c.revision_id.in_(revision_ids))
            .order_by(evidence.c.evidence_id),
        )
        links = _bounded_rows(
            session,
            select(claim_evidence)
            .where(claim_evidence.c.claim_id.in_(claim_ids))
            .order_by(claim_evidence.c.claim_id, claim_evidence.c.evidence_id),
        )
        assertions = _bounded_rows(
            session,
            select(claim_assertions)
            .where(claim_assertions.c.claim_id.in_(claim_ids))
            .order_by(claim_assertions.c.assertion_id),
        )
        result_rows = _bounded_rows(
            session,
            select(enrichment_results)
            .where(
                enrichment_results.c.event_id == str(event_id),
                enrichment_results.c.is_current.is_(True),
            )
            .order_by(enrichment_results.c.result_id),
        )
        source_ids = {row["source_id"] for row in parent_rows}
        for row in result_rows:
            declared_sources = row["source_scope"]
            if not isinstance(declared_sources, list) or any(
                not isinstance(identifier, str) for identifier in declared_sources
            ):
                raise ValueError("dimension source identities invalid")
            source_ids.update(declared_sources)
        source_ids.update(row["source_id"] for row in assertions)
        if len(source_ids) > MAX_PARENT_ROWS:
            raise ReadCandidateLimitError("source closure exceeds fixed bound")
        source_rows = _bounded_rows(
            session,
            select(sources, reader._visible(sources).label("visible"))
            .where(sources.c.source_id.in_(source_ids))
            .order_by(sources.c.source_id),
        )
        extra_revisions = {row["revision_id"] for row in assertions} - set(revision_ids)
        if extra_revisions:
            raise ReadCandidateLimitError("assertion parents outside bounded event closure")
        evidence_ids = {row["evidence_id"] for row in evidence_rows}
        if any(row["evidence_id"] not in evidence_ids for row in links):
            raise ReadCandidateLimitError("evidence parents outside bounded event closure")
        external_rows = _bounded_rows(
            session,
            select(event_external_ids)
            .where(event_external_ids.c.event_id == str(event_id))
            .order_by(event_external_ids.c.id_type, event_external_ids.c.id_value),
        )
        inputs = GraphReadInputs(
            event_id,
            reader.scope,
            tuple(sorted(source_ids)),
            tuple(sorted({row["document_id"] for row in parent_rows})),
            revision_ids,
            claim_ids,
            tuple(sorted(evidence_ids)),
            tuple(
                sorted({row["block_id"] for row in evidence_rows if row["block_id"] is not None})
            ),
            tuple(row["assertion_id"] for row in assertions),
            tuple((row["claim_id"], row["evidence_id"]) for row in links),
        )
        all_visible = all(
            row["visible"] is True
            for row in (*parent_rows, *claim_rows, *evidence_rows, *source_rows)
        ) and len(source_rows) == len(source_ids)
        material = [
            dict(event_row),
            *[
                [dict(row) for row in rows]
                for rows in (
                    parent_rows,
                    claim_rows,
                    evidence_rows,
                    links,
                    assertions,
                    result_rows,
                    source_rows,
                    external_rows,
                )
            ],
        ]
        return _EventInputs(
            inputs,
            _fingerprint(material),
            all_visible,
            tuple(row["result_id"] for row in result_rows),
            tuple((row["id_type"], row["id_value"]) for row in external_rows),
        )

    def _lock_event_inputs(self, reader: KnowledgeReadService, inputs: _EventInputs) -> None:
        session = reader.session
        EvidenceGraphReadService(session, reader.scope).lock_graph_inputs(
            inputs.graph.event_id, inputs.graph
        )
        session.execute(
            select(enrichment_results.c.result_id)
            .where(enrichment_results.c.result_id.in_(inputs.result_ids))
            .order_by(enrichment_results.c.result_id)
            .with_for_update(read=True)
        ).all()
        session.execute(
            select(event_external_ids.c.id_value)
            .where(
                event_external_ids.c.event_id == str(inputs.graph.event_id),
                tuple_(event_external_ids.c.id_type, event_external_ids.c.id_value).in_(
                    inputs.external_ids
                ),
            )
            .order_by(event_external_ids.c.id_type, event_external_ids.c.id_value)
            .with_for_update(read=True)
        ).all()
        if self._event_inputs(reader, inputs.graph.event_id).fingerprint != inputs.fingerprint:
            raise ReadSnapshotChangedError("event read inputs changed")

    def _advisory(
        self, session: Session, scope: AccessScope, arguments: GetAdvisoryArguments
    ) -> ReadToolOutcome:
        reader = KnowledgeReadService(session, scope, self._data_mode)
        inputs = self._event_inputs(reader, arguments.event_id)
        candidate = reader.event_detail(arguments.event_id)
        self._lock_event_inputs(reader, inputs)
        current = reader.event_detail(arguments.event_id)
        if current != candidate:
            raise ReadSnapshotChangedError("advisory projection changed")
        incomplete = not inputs.all_visible or not current.revisions
        return ReadToolOutcome(
            current,
            ToolStatus.PARTIAL if incomplete else ToolStatus.SUCCEEDED,
            "advisory_scope_incomplete" if incomplete else None,
            None,
            ("读取已入库事件资料及原始状态；引用或supported记录不证明任意模型论断。",),
        )

    def _inventory(
        self, session: Session, scope: AccessScope, arguments: GetInventoryArguments
    ) -> ReadToolOutcome:
        reader = InventoryService(session, scope)
        candidate = reader.get_snapshot(str(arguments.asset_id), str(arguments.snapshot_id))
        asset = (
            session.execute(
                select(assets)
                .where(
                    assets.c.asset_id == str(arguments.asset_id),
                    assets.c.tenant_id == scope.tenant_id,
                )
                .with_for_update(read=True)
            )
            .mappings()
            .first()
        )
        if asset is None:
            raise CrossTenantAccessError("resource not found")
        session.execute(
            select(asset_snapshots.c.snapshot_id)
            .where(
                asset_snapshots.c.asset_id == str(arguments.asset_id),
                asset_snapshots.c.snapshot_id == str(arguments.snapshot_id),
                asset_snapshots.c.tenant_id == scope.tenant_id,
            )
            .with_for_update(read=True)
        ).one()
        current = reader.get_snapshot(str(arguments.asset_id), str(arguments.snapshot_id))
        if candidate != current:
            raise ReadSnapshotChangedError("asset snapshot changed")
        stale = asset["current_snapshot_id"] != str(arguments.snapshot_id) or not asset["active"]
        incomplete = current.inventory_completeness != "complete_for_declared_scope"
        code = (
            "inventory_snapshot_not_current"
            if stale
            else ("inventory_scope_incomplete" if incomplete else None)
        )
        return ReadToolOutcome(
            current,
            ToolStatus.PARTIAL if stale or incomplete else ToolStatus.SUCCEEDED,
            code,
            current.observed_at,
            ("仅所指定租户资产快照与声明范围；未知或未列出的组件不代表安全。",),
        )

    def _changes(
        self, session: Session, scope: AccessScope, arguments: FindChangesArguments
    ) -> ReadToolOutcome:
        reader = KnowledgeReadService(session, scope, self._data_mode)
        inputs = self._event_inputs(reader, arguments.event_id)
        self._lock_event_inputs(reader, inputs)
        epochs = EvidenceGraphReadService(session, scope).read_scope_epochs()
        filters = EventFilters(
            q=str(arguments.event_id),
            product=_fingerprint([inputs.fingerprint, epochs]),
            risk_type=f"r14-changes-{arguments.limit}",
        )
        related_ids = [str(arguments.event_id), *inputs.graph.claim_ids]
        query = select(
            change_events.c.change_id,
            change_events.c.epoch,
            change_events.c.change_type,
            change_events.c.created_at,
            case(
                (
                    func.jsonb_typeof(change_events.c.entity_ids) == "array",
                    func.jsonb_array_length(change_events.c.entity_ids),
                ),
                else_=-1,
            ).label("identity_count"),
            change_events.c.created_at.label("first_seen_at"),
            change_events.c.change_id.label("event_id"),
        ).where(
            change_events.c.scope_key == "public",
            change_events.c.entity_ids.op("?|")(array(related_ids)),
        )
        if arguments.cursor is not None:
            try:
                position = decode_event_cursor(arguments.cursor, filters)
            except InvalidEventCursor as error:
                raise ReadSnapshotChangedError("cursor invalid or stale") from error
            query = query.where(
                tuple_(change_events.c.created_at, change_events.c.change_id)
                < tuple_(position.first_seen_at, str(position.event_id))
            )
        rows = list(
            session.execute(
                query.order_by(change_events.c.created_at.desc(), change_events.c.change_id.desc())
                .limit(MAX_CHANGE_CANDIDATES + 1)
                .with_for_update(read=True)
            ).mappings()
        )
        items: list[ChangeSummary] = []
        scanned = 0
        incomplete = not inputs.all_visible
        for row in rows[:MAX_CHANGE_CANDIDATES]:
            scanned += 1
            if not inputs.all_visible:
                continue
            identity_count = row["identity_count"]
            if not isinstance(identity_count, int) or not 0 <= identity_count <= MAX_PARENT_ROWS:
                incomplete = True
                continue
            try:
                summary = ChangeSummary(
                    change_id=row["change_id"],
                    change_type=row["change_type"],
                    knowledge_epoch=row["epoch"],
                    recorded_at=row["created_at"],
                )
            except ValueError:
                incomplete = True
                continue
            items.append(summary)
            if len(items) == arguments.limit:
                break
        has_more = len(rows) > scanned
        incomplete = incomplete or (scanned == MAX_CHANGE_CANDIDATES and has_more)
        cursor = encode_event_cursor(rows[scanned - 1], filters) if has_more and scanned else None
        page = ChangesPage(
            event_id=arguments.event_id,
            items=tuple(items),
            next_cursor=cursor,
            data_mode=self._data_mode,
        )
        status = (
            ToolStatus.PARTIAL
            if incomplete
            else (ToolStatus.SUCCEEDED if items else ToolStatus.NO_RESULT)
        )
        return ReadToolOutcome(
            page,
            status,
            "change_history_incomplete" if incomplete else None,
            None,
            ("仅当前可见公开事件的有界持久变化摘要；未返回全历史或已撤销来源标识。",),
        )

    def read_tool(
        self,
        principal: Principal,
        scope: AccessScope,
        call: SharedReadCall,
        deadline_monotonic: float,
    ) -> ReadToolOutcome:
        permission = READ_ASSET if isinstance(call, GetInventoryCall) else READ_PUBLIC
        if permission == READ_PUBLIC and scope.tenant_id is not None:
            raise PermissionDeniedError("public read requires public scope")
        with self._authenticated_read(principal, scope, permission, deadline_monotonic) as (
            session,
            effective,
        ):
            if isinstance(call, GetAdvisoryCall) and isinstance(
                call.arguments, GetAdvisoryArguments
            ):
                return self._advisory(session, effective, call.arguments)
            if isinstance(call, GetInventoryCall) and isinstance(
                call.arguments, GetInventoryArguments
            ):
                return self._inventory(session, effective, call.arguments)
            if isinstance(call, FindChangesCall) and isinstance(
                call.arguments, FindChangesArguments
            ):
                return self._changes(session, effective, call.arguments)
            raise ValueError("required business identifiers missing")
