"""Immutable PG-derived graph batches, paged reconciliation and replay-safe acknowledgments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import and_, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from ai_intel.domain.access import (
    READ_ASSET,
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.evidence_graph import (
    GRAPH_RULE_VERSION,
    RELATION_TYPES,
    EvidenceGraphReadService,
    GraphSnapshot,
    GraphSnapshotChangedError,
    RelationType,
)
from ai_intel.knowledge.graph_projection_models import (
    graph_projection_batches,
    graph_projection_state,
)
from ai_intel.knowledge.persistence_models import events
from ai_intel.workers.executor import (
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
    JobHandler,
)

MAX_BATCH_BYTES = 8 * 1024 * 1024
MANIFEST_PAGE_SIZE = 100
GRAPH_APPLY_JOB_TYPE = "graph_apply"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Namespace = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
EpochMap = tuple[tuple[str, int], ...]
ApplyOutcome = Literal["applied", "already_applied", "superseded"]
NodeKind = Literal["event", "source_revision", "component_version", "atlas", "paper", "remediation"]


class ProjectionCapacityError(RuntimeError):
    """A bounded export is incomplete; it must not advance a complete watermark."""


class ProjectionDigestConflict(RuntimeError):
    """Stored immutable bytes or a same-sequence receipt disagree."""


class ProjectionNotReady(RuntimeError):
    """A requested manifest is absent, incomplete or behind authoritative epochs."""


class ProjectionRecord(StrictRecord):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def reject_coerced_schema_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema version requires an integer")
        return value


def partition_for_scope(scope: AccessScope) -> str:
    scope.requires(READ_PUBLIC)
    if scope.tenant_id is not None and READ_ASSET in scope.permissions:
        if not scope.tenant_id.strip() or len(scope.tenant_id) > 200:
            raise PermissionDeniedError("invalid projection scope")
        return "tenant:" + scope.tenant_id
    return "public"


def _validate_epochs(partition_key: str, epochs: EpochMap) -> None:
    expected = {"public"}
    if partition_key != "public":
        if not partition_key.startswith("tenant:") or not partition_key[7:].strip():
            raise ValueError("invalid projection partition")
        expected.add(partition_key)
    if (
        tuple(sorted(epochs)) != epochs
        or {key for key, _ in epochs} != expected
        or len(epochs) != len(expected)
        or any(type(epoch) is not int or epoch < 1 for _, epoch in epochs)
    ):
        raise ValueError("projection epoch map unavailable")


class ProjectedNode(ProjectionRecord):
    id: UUID
    kind: NodeKind
    scope: VisibilityScope


class ProjectedEdge(ProjectionRecord):
    id: UUID
    relation_type: RelationType
    subject_id: UUID
    object_id: UUID
    scope: VisibilityScope
    source_revision_ids: tuple[UUID, ...] = Field(min_length=1, max_length=2000)
    evidence_span_ids: tuple[UUID, ...] = Field(min_length=1, max_length=2000)
    supporting_claim_ids: tuple[UUID, ...] = Field(min_length=1, max_length=2000)
    rule_or_model_version: Literal["r10-graph-1.2.0"] = GRAPH_RULE_VERSION


class GraphProjectionBatch(ProjectionRecord):
    schema_version: Literal[1] = 1
    batch_id: UUID
    namespace: Namespace
    partition_key: str = Field(min_length=1, max_length=207)
    generation_id: UUID
    event_id: UUID
    sequence: int = Field(ge=1)
    kind: Literal["snapshot", "tombstone"]
    event_business_version: int | None = Field(default=None, ge=1)
    scope_epochs: EpochMap
    rule_version: Literal["r10-graph-1.2.0"] = GRAPH_RULE_VERSION
    input_sha256: Digest
    full_graph_sha256: Digest
    nodes: tuple[ProjectedNode, ...] = Field(max_length=200)
    edges: tuple[ProjectedEdge, ...] = Field(max_length=400)
    captured_at: datetime

    @model_validator(mode="after")
    def validate_complete_projection(self) -> GraphProjectionBatch:
        _validate_epochs(self.partition_key, self.scope_epochs)
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("projection timestamps require timezone")
        if self.kind == "tombstone":
            if self.nodes or self.edges or self.event_business_version is not None:
                raise ValueError("tombstone contains graph content")
            return self
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes) or len({edge.id for edge in self.edges}) != len(
            self.edges
        ):
            raise ValueError("duplicate graph identity")
        root = nodes.get(self.event_id)
        if root is None or root.kind != "event" or self.event_business_version is None:
            raise ValueError("snapshot root unavailable")
        scoped_values: tuple[ProjectedNode | ProjectedEdge, ...] = (*self.nodes, *self.edges)
        for value in scoped_values:
            if value.scope.visibility == "tenant" and (
                self.partition_key != "tenant:" + str(value.scope.tenant_id)
            ):
                raise ValueError("graph content exceeds partition")
        endpoints = {
            "same_event": ("event", "source_revision"),
            "affects_component_version": ("event", "component_version"),
            "mapped_atlas": ("event", "atlas"),
            "related_paper": ("event", "paper"),
            "remediated_by": ("event", "remediation"),
            "component_version_vulnerability": ("component_version", "event"),
        }
        for edge in self.edges:
            subject, target = nodes.get(edge.subject_id), nodes.get(edge.object_id)
            if subject is None or target is None:
                raise ValueError("graph edge has absent endpoint")
            if (subject.kind, target.kind) != endpoints[edge.relation_type]:
                raise ValueError("graph edge endpoint kind disagrees")
            if self.event_id not in (edge.subject_id, edge.object_id):
                raise ValueError("graph edge belongs to another event")
            if edge.scope.visibility == "public" and any(
                node.scope.visibility != "public" for node in (subject, target)
            ):
                raise ValueError("private graph content promoted to public")
            for identifiers in (
                edge.source_revision_ids,
                edge.evidence_span_ids,
                edge.supporting_claim_ids,
            ):
                if tuple(sorted(set(identifiers))) != identifiers:
                    raise ValueError("support identities are not canonical")
        return self


class ManifestEntry(ProjectionRecord):
    event_id: UUID
    business_version: int | None = Field(default=None, ge=1)


class ManifestPage(ProjectionRecord):
    page_number: int = Field(ge=0)
    entries: tuple[ManifestEntry, ...] = Field(min_length=1, max_length=MANIFEST_PAGE_SIZE)


class ReconciliationManifest(ProjectionRecord):
    schema_version: Literal[1] = 1
    namespace: Namespace
    partition_key: str = Field(min_length=1, max_length=207)
    generation_id: UUID
    scope_epochs: EpochMap
    rule_version: Literal["r10-graph-1.2.0"] = GRAPH_RULE_VERSION
    manifest_sha256: Digest
    page_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    captured_count: int = Field(default=0, ge=0)
    acknowledged_count: int = Field(default=0, ge=0)
    status: Literal["pending", "ready", "stale"] = "pending"

    @model_validator(mode="after")
    def validate_counts(self) -> ReconciliationManifest:
        _validate_epochs(self.partition_key, self.scope_epochs)
        if self.page_count != (self.event_count + MANIFEST_PAGE_SIZE - 1) // MANIFEST_PAGE_SIZE:
            raise ValueError("manifest page count disagrees")
        if not 0 <= self.acknowledged_count <= self.captured_count <= self.event_count:
            raise ValueError("manifest counts disagree")
        if self.status == "ready" and self.acknowledged_count != self.event_count:
            raise ValueError("manifest incomplete")
        return self


class ProjectionSlot(ProjectionRecord):
    event_id: UUID
    captured_sequence: int = Field(default=0, ge=0)
    acknowledged_sequence: int = Field(default=0, ge=0)
    batch_id: UUID | None = None
    payload_sha256: Digest | None = None
    acknowledged_sha256: Digest | None = None


class ProjectionReceipt(ProjectionRecord):
    batch_id: UUID
    sequence: int = Field(ge=1)
    payload_sha256: Digest
    outcome: ApplyOutcome


class GraphCandidate(ProjectionRecord):
    edge_id: UUID
    event_id: UUID
    sequence: int = Field(ge=1)
    payload_sha256: Digest


class GraphCandidateSet(ProjectionRecord):
    candidates: tuple[GraphCandidate, ...] = Field(max_length=400)
    truncated: bool
    requires_pg_revalidation: Literal[True] = True

    @field_validator("requires_pg_revalidation", mode="before")
    @classmethod
    def reject_coerced_revalidation_flag(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("revalidation flag requires a boolean")
        return value


class ProjectionHistoryEntry(ProjectionRecord):
    batch_id: UUID
    generation_id: UUID
    event_id: UUID
    sequence: int = Field(ge=1)
    kind: Literal["snapshot", "tombstone"]
    captured_at: datetime
    payload_sha256: Digest


class GraphProjectionStore(Protocol):
    def apply_batch(self, batch: GraphProjectionBatch, digest: str) -> ProjectionReceipt: ...

    def find_candidates(
        self,
        scope: AccessScope,
        namespace: str,
        generation_id: UUID,
        seed_node_ids: tuple[UUID, ...],
        relation_types: tuple[RelationType, ...],
        max_hops: int,
    ) -> GraphCandidateSet: ...


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def encode_projection_batch(batch: GraphProjectionBatch) -> tuple[bytes, str]:
    validated = GraphProjectionBatch.model_validate_json(batch.model_dump_json())
    payload = _canonical_bytes(validated.model_dump(mode="json"))
    if len(payload) > MAX_BATCH_BYTES:
        raise ProjectionCapacityError("graph_projection_capacity_exceeded")
    return payload, hashlib.sha256(payload).hexdigest()


def decode_projection_batch(payload: bytes, digest: str) -> GraphProjectionBatch:
    if len(payload) > MAX_BATCH_BYTES:
        raise ProjectionCapacityError("graph_projection_capacity_exceeded")
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ProjectionDigestConflict("graph_projection_digest_conflict")
    try:
        batch = GraphProjectionBatch.model_validate_json(payload)
    except ValidationError:
        raise ProjectionDigestConflict("graph_projection_payload_invalid") from None
    if encode_projection_batch(batch)[0] != payload:
        raise ProjectionDigestConflict("graph_projection_payload_not_canonical")
    return batch


def make_projection_batch(
    snapshot: GraphSnapshot,
    *,
    namespace: str,
    partition_key: str,
    generation_id: UUID,
    sequence: int,
    scope_epochs: EpochMap,
    input_sha256: str,
    captured_at: datetime,
) -> GraphProjectionBatch:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("projection timestamps require timezone")
    if snapshot.truncated:
        raise ProjectionCapacityError("graph_projection_capacity_exceeded")
    batch = GraphProjectionBatch(
        batch_id=uuid4(),
        namespace=namespace,
        partition_key=partition_key,
        generation_id=generation_id,
        event_id=snapshot.event_id,
        sequence=sequence,
        kind="snapshot",
        event_business_version=snapshot.business_version,
        scope_epochs=scope_epochs,
        input_sha256=input_sha256,
        full_graph_sha256=snapshot.content_sha256,
        nodes=tuple(
            ProjectedNode(id=node.id, kind=node.kind, scope=node.scope) for node in snapshot.nodes
        ),
        edges=tuple(
            ProjectedEdge.model_validate(edge.model_dump(exclude={"reason", "status"}))
            for edge in snapshot.edges
        ),
        captured_at=captured_at.astimezone(UTC),
    )
    encode_projection_batch(batch)
    return batch


def projection_apply_decision(
    current_sequence: int,
    incoming_sequence: int,
    stored_digest: str,
    incoming_digest: str,
) -> ApplyOutcome:
    if type(current_sequence) is not int or current_sequence < 0:
        raise ProjectionDigestConflict("graph_projection_marker_invalid")
    if type(incoming_sequence) is not int or incoming_sequence < 1:
        raise ProjectionDigestConflict("graph_projection_sequence_invalid")
    if incoming_sequence < current_sequence:
        return "superseded"
    if incoming_sequence == current_sequence:
        if stored_digest != incoming_digest:
            raise ProjectionDigestConflict("graph_projection_digest_conflict")
        return "already_applied"
    return "applied"


def _body[StateRecord: ProjectionRecord](model: type[StateRecord], row: RowMapping) -> StateRecord:
    return model.model_validate_json(json.dumps(row["body"]))


def _state_query(
    namespace: str,
    partition_key: str,
    generation_id: UUID,
    state_key: str,
) -> Select[tuple[object, ...]]:
    return select(graph_projection_state).where(
        graph_projection_state.c.namespace == namespace,
        graph_projection_state.c.partition_key == partition_key,
        graph_projection_state.c.generation_id == str(generation_id),
        graph_projection_state.c.state_key == state_key,
    )


def _state_row(
    session: Session,
    namespace: str,
    partition_key: str,
    generation_id: UUID,
    state_key: str,
    *,
    lock: bool = False,
) -> RowMapping:
    query = _state_query(namespace, partition_key, generation_id, state_key)
    if lock:
        query = query.with_for_update()
    row = session.execute(query).mappings().first()
    if row is None:
        raise ProjectionNotReady("graph_projection_state_unavailable")
    return row


def _save_state(
    session: Session,
    namespace: str,
    partition_key: str,
    generation_id: UUID,
    state_key: str,
    state_kind: str,
    value: ProjectionRecord,
    now: datetime,
    event_id: UUID | None = None,
) -> None:
    session.execute(
        insert(graph_projection_state).values(
            namespace=namespace,
            partition_key=partition_key,
            generation_id=str(generation_id),
            state_key=state_key,
            state_kind=state_kind,
            event_id=None if event_id is None else str(event_id),
            body=value.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
        )
    )


def _update_state(
    session: Session, row: RowMapping, value: ProjectionRecord, now: datetime
) -> None:
    session.execute(
        update(graph_projection_state)
        .where(
            *(
                graph_projection_state.c[key] == row[key]
                for key in (
                    "namespace",
                    "partition_key",
                    "generation_id",
                    "state_key",
                )
            )
        )
        .values(body=value.model_dump(mode="json"), updated_at=now)
    )


def _visible_events(scope: AccessScope) -> ColumnElement[bool]:
    public = and_(events.c.visibility == "public", events.c.tenant_id.is_(None))
    if partition_for_scope(scope) == "public":
        return public
    return or_(public, and_(events.c.visibility == "tenant", events.c.tenant_id == scope.tenant_id))


def _epochs(session: Session, scope: AccessScope, *, lock: bool = False) -> EpochMap:
    partition = partition_for_scope(scope)
    try:
        epochs = EvidenceGraphReadService(session, scope).read_scope_epochs(lock=lock)
        _validate_epochs(partition, epochs)
    except ValueError:
        raise ProjectionNotReady("graph_projection_epoch_unavailable") from None
    return epochs


def _manifest_entries(
    session: Session,
    manifest: ReconciliationManifest,
) -> tuple[ManifestEntry, ...]:
    rows = session.execute(
        select(graph_projection_state).where(
            graph_projection_state.c.namespace == manifest.namespace,
            graph_projection_state.c.partition_key == manifest.partition_key,
            graph_projection_state.c.generation_id == str(manifest.generation_id),
            graph_projection_state.c.state_kind == "page",
        )
    ).mappings()
    pages = sorted((_body(ManifestPage, row) for row in rows), key=lambda page: page.page_number)
    if [page.page_number for page in pages] != list(range(manifest.page_count)):
        raise ProjectionNotReady("graph_manifest_pages_incomplete")
    entries = tuple(entry for page in pages for entry in page.entries)
    if len(entries) != manifest.event_count or len({entry.event_id for entry in entries}) != len(
        entries
    ):
        raise ProjectionNotReady("graph_manifest_entries_incomplete")
    if tuple(sorted(entries, key=lambda entry: entry.event_id)) != entries:
        raise ProjectionDigestConflict("graph_manifest_order_invalid")
    digest = hashlib.sha256(
        _canonical_bytes(
            {
                "epochs": manifest.scope_epochs,
                "rule": manifest.rule_version,
                "entries": [entry.model_dump(mode="json") for entry in entries],
            }
        )
    ).hexdigest()
    if digest != manifest.manifest_sha256:
        raise ProjectionDigestConflict("graph_manifest_digest_conflict")
    return entries


def begin_reconciliation(
    session: Session,
    scope: AccessScope,
    namespace: str,
    generation_id: UUID,
    now: datetime,
) -> ReconciliationManifest:
    """Capture a complete event/old-slot manifest in one caller-owned RR transaction."""
    if session.connection().get_isolation_level() != "REPEATABLE READ":
        raise ValueError("manifest requires repeatable read")
    partition = partition_for_scope(scope)
    epochs = _epochs(session, scope)
    existing = session.execute(_state_query(namespace, partition, generation_id, "partition"))
    row = existing.mappings().first()
    if row is not None:
        manifest = _body(ReconciliationManifest, row)
        _manifest_entries(session, manifest)
        if manifest.scope_epochs != epochs:
            raise ProjectionNotReady("graph_manifest_epoch_changed")
        return manifest
    current: dict[str, int] = dict(
        session.execute(
            select(events.c.event_id, events.c.business_version).where(
                _visible_events(scope),
                events.c.status == "active",
            )
        ).all()
    )
    old_ids: set[str] = set(
        session.scalars(
            select(graph_projection_state.c.event_id).where(
                graph_projection_state.c.namespace == namespace,
                graph_projection_state.c.partition_key == partition,
                graph_projection_state.c.state_kind == "slot",
            )
        )
    )
    entries = tuple(
        ManifestEntry(event_id=UUID(event_id), business_version=current.get(event_id))
        for event_id in sorted(set(current) | old_ids)
    )
    manifest_hash = hashlib.sha256(
        _canonical_bytes(
            {
                "epochs": epochs,
                "rule": GRAPH_RULE_VERSION,
                "entries": [entry.model_dump(mode="json") for entry in entries],
            }
        )
    ).hexdigest()
    pages = tuple(
        ManifestPage(
            page_number=index // MANIFEST_PAGE_SIZE,
            entries=entries[index : index + MANIFEST_PAGE_SIZE],
        )
        for index in range(0, len(entries), MANIFEST_PAGE_SIZE)
    )
    manifest = ReconciliationManifest(
        namespace=namespace,
        partition_key=partition,
        generation_id=generation_id,
        scope_epochs=epochs,
        manifest_sha256=manifest_hash,
        page_count=len(pages),
        event_count=len(entries),
        status="ready" if not entries else "pending",
    )
    _save_state(
        session, namespace, partition, generation_id, "partition", "partition", manifest, now
    )
    for page in pages:
        _save_state(
            session,
            namespace,
            partition,
            generation_id,
            f"page:{page.page_number}",
            "page",
            page,
            now,
        )
    return manifest


def read_manifest_page(
    session: Session,
    scope: AccessScope,
    namespace: str,
    generation_id: UUID,
    page_number: int,
) -> ManifestPage:
    if type(page_number) is not int or page_number < 0:
        raise ValueError("invalid manifest page")
    return _body(
        ManifestPage,
        _state_row(
            session,
            namespace,
            partition_for_scope(scope),
            generation_id,
            f"page:{page_number}",
        ),
    )


def _manifest_entry(
    session: Session,
    scope: AccessScope,
    namespace: str,
    generation_id: UUID,
    event_id: UUID,
) -> ManifestEntry:
    partition = partition_for_scope(scope)
    manifest = _body(
        ReconciliationManifest,
        _state_row(
            session,
            namespace,
            partition,
            generation_id,
            "partition",
        ),
    )
    for entry in _manifest_entries(session, manifest):
        if entry.event_id == event_id:
            return entry
    raise ProjectionNotReady("graph_event_outside_manifest")


ScopeAuthorizer = Callable[[Session], AccessScope]


def capture_event_projection(
    engine: Engine,
    scope: AccessScope,
    namespace: str,
    generation_id: UUID,
    event_id: UUID,
    *,
    authorize: ScopeAuthorizer,
    captured_at: datetime,
) -> GraphProjectionBatch:
    """RR candidate then fresh locked PG fence; the caller supplies real current authorization."""
    partition = partition_for_scope(scope)
    with Session(engine) as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        entry = _manifest_entry(session, scope, namespace, generation_id, event_id)
        reader = EvidenceGraphReadService(session, scope)
        epochs = _epochs(session, scope)
        snapshot = reader.event_graph(event_id) if entry.business_version is not None else None
        if snapshot is not None and snapshot.truncated:
            raise ProjectionCapacityError("graph_projection_capacity_exceeded")
        input_hash, inputs = reader.input_sha256, reader.read_inputs
    with Session(engine) as session, session.begin():
        session.connection(execution_options={"isolation_level": "READ COMMITTED"})
        if authorize(session) != scope:
            raise PermissionDeniedError("graph authorization changed")
        reader = EvidenceGraphReadService(session, scope)
        if snapshot is not None:
            if inputs is None:
                raise GraphSnapshotChangedError("graph read inputs missing")
            reader.lock_graph_inputs(event_id, inputs)
            fresh = reader.event_graph(event_id)
            if reader.input_sha256 != input_hash or fresh != snapshot:
                raise GraphSnapshotChangedError("graph snapshot changed")
        else:
            visible = session.scalar(
                select(events.c.event_id)
                .where(
                    events.c.event_id == str(event_id),
                    _visible_events(scope),
                    events.c.status == "active",
                )
                .with_for_update(read=True)
            )
            if visible is not None:
                raise GraphSnapshotChangedError("graph tombstone became visible")
        current_epochs = _epochs(session, scope, lock=True)
        if current_epochs != epochs:
            raise GraphSnapshotChangedError("graph epoch changed")
        header = _state_row(session, namespace, partition, generation_id, "partition", lock=True)
        manifest = _body(ReconciliationManifest, header)
        if manifest.scope_epochs != epochs or manifest.status == "stale":
            raise ProjectionNotReady("graph_manifest_epoch_changed")
        if snapshot is not None and snapshot.business_version != entry.business_version:
            raise GraphSnapshotChangedError("event version changed")
        key = "event:" + str(event_id)
        session.execute(
            insert(graph_projection_state)
            .values(
                namespace=namespace,
                partition_key=partition,
                generation_id=str(generation_id),
                state_key=key,
                state_kind="slot",
                event_id=str(event_id),
                body=ProjectionSlot(event_id=event_id).model_dump(mode="json"),
                created_at=captured_at,
                updated_at=captured_at,
            )
            .on_conflict_do_nothing()
        )
        slot_row = _state_row(session, namespace, partition, generation_id, key, lock=True)
        slot = _body(ProjectionSlot, slot_row)
        if slot.batch_id is not None:
            return read_projection_batch(session, scope, slot.batch_id)[0]
        sequence = slot.captured_sequence + 1
        if snapshot is not None and input_hash is not None:
            batch = make_projection_batch(
                snapshot,
                namespace=namespace,
                partition_key=partition,
                generation_id=generation_id,
                sequence=sequence,
                scope_epochs=epochs,
                input_sha256=input_hash,
                captured_at=captured_at,
            )
        else:
            empty_hash = hashlib.sha256(
                _canonical_bytes({"event_id": str(event_id), "epochs": epochs})
            ).hexdigest()
            batch = GraphProjectionBatch(
                batch_id=uuid4(),
                namespace=namespace,
                partition_key=partition,
                generation_id=generation_id,
                event_id=event_id,
                sequence=sequence,
                kind="tombstone",
                scope_epochs=epochs,
                input_sha256=empty_hash,
                full_graph_sha256=empty_hash,
                nodes=(),
                edges=(),
                captured_at=captured_at,
            )
        payload, digest = encode_projection_batch(batch)
        session.execute(
            insert(graph_projection_batches).values(
                batch_id=str(batch.batch_id),
                namespace=namespace,
                partition_key=partition,
                generation_id=str(generation_id),
                event_id=str(event_id),
                sequence=sequence,
                kind=batch.kind,
                payload_sha256=digest,
                payload=payload,
                captured_at=captured_at,
            )
        )
        enqueue_job(
            session,
            scope.tenant_id if partition != "public" else None,
            GRAPH_APPLY_JOB_TYPE,
            _canonical_bytes({"batch_id": str(batch.batch_id)}),
            captured_at,
            idempotency_key="graph-apply:" + str(batch.batch_id),
        )
        _update_state(
            session,
            slot_row,
            ProjectionSlot(
                event_id=event_id,
                captured_sequence=sequence,
                batch_id=batch.batch_id,
                payload_sha256=digest,
            ),
            captured_at,
        )
        _update_state(
            session,
            header,
            manifest.model_copy(
                update={
                    "captured_count": manifest.captured_count + 1,
                }
            ),
            captured_at,
        )
        return batch


def read_projection_batch(
    session: Session,
    scope: AccessScope,
    batch_id: UUID,
) -> tuple[GraphProjectionBatch, str]:
    row = (
        session.execute(
            select(graph_projection_batches).where(
                graph_projection_batches.c.batch_id == str(batch_id),
                graph_projection_batches.c.partition_key == partition_for_scope(scope),
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise CrossTenantAccessError("resource not found")
    digest = str(row["payload_sha256"])
    batch = decode_projection_batch(bytes(row["payload"]), digest)
    if any(
        str(getattr(batch, key)) != str(row[key])
        for key in (
            "batch_id",
            "namespace",
            "partition_key",
            "generation_id",
            "event_id",
            "sequence",
            "kind",
        )
    ):
        raise ProjectionDigestConflict("graph_projection_columns_disagree")
    return batch, digest


def apply_projection_batch(
    session: Session,
    scope: AccessScope,
    batch_id: UUID,
    store: GraphProjectionStore,
    now: datetime,
) -> ProjectionReceipt:
    """Neo4j commits first; caller PG rollback can only cause safe immutable replay."""
    batch, digest = read_projection_batch(session, scope, batch_id)
    current_epochs = _epochs(session, scope, lock=True)
    header = _state_row(
        session, batch.namespace, batch.partition_key, batch.generation_id, "partition", lock=True
    )
    manifest = _body(ReconciliationManifest, header)
    _manifest_entries(session, manifest)
    slot_row = _state_row(
        session,
        batch.namespace,
        batch.partition_key,
        batch.generation_id,
        "event:" + str(batch.event_id),
        lock=True,
    )
    slot = _body(ProjectionSlot, slot_row)
    receipt = store.apply_batch(batch, digest)
    if (receipt.batch_id, receipt.sequence, receipt.payload_sha256) != (
        batch.batch_id,
        batch.sequence,
        digest,
    ):
        raise ProjectionDigestConflict("graph_projection_receipt_disagrees")
    if receipt.outcome == "superseded":
        raise ProjectionNotReady("graph_projection_marker_ahead_of_pg")
    if slot.acknowledged_sequence == batch.sequence:
        if slot.acknowledged_sha256 != digest:
            raise ProjectionDigestConflict("graph_projection_ack_disagrees")
        return receipt
    if slot.batch_id != batch.batch_id or slot.captured_sequence != batch.sequence:
        raise ProjectionDigestConflict("graph_projection_slot_disagrees")
    _update_state(
        session,
        slot_row,
        slot.model_copy(
            update={
                "acknowledged_sequence": batch.sequence,
                "acknowledged_sha256": digest,
            }
        ),
        now,
    )
    acknowledged = manifest.acknowledged_count + 1
    status: Literal["pending", "ready", "stale"] = "pending"
    if current_epochs != manifest.scope_epochs:
        status = "stale"
    elif acknowledged == manifest.event_count:
        status = "ready"
    _update_state(
        session,
        header,
        manifest.model_copy(
            update={
                "acknowledged_count": acknowledged,
                "status": status,
            }
        ),
        now,
    )
    return receipt


def read_projection_candidates(
    session: Session,
    scope: AccessScope,
    namespace: str,
    generation_id: UUID,
    seed_node_ids: tuple[UUID, ...],
    store: GraphProjectionStore,
    *,
    relation_types: tuple[RelationType, ...] = RELATION_TYPES,
    max_hops: int = 2,
) -> GraphCandidateSet:
    """Return bounded identifiers only; final public output still requires the PG graph fence."""
    if not 1 <= len(seed_node_ids) <= 20 or any(type(value) is not UUID for value in seed_node_ids):
        raise ValueError("invalid graph seeds")
    if type(max_hops) is not int or max_hops not in (1, 2):
        raise ValueError("graph hops outside bounds")
    if not relation_types or any(value not in RELATION_TYPES for value in relation_types):
        raise ValueError("invalid graph relation")
    partition = partition_for_scope(scope)
    epochs = _epochs(session, scope)
    manifest = _body(
        ReconciliationManifest,
        _state_row(
            session,
            namespace,
            partition,
            generation_id,
            "partition",
        ),
    )
    _manifest_entries(session, manifest)
    if manifest.status != "ready" or manifest.scope_epochs != epochs:
        raise ProjectionNotReady("graph_projection_not_current")
    found = store.find_candidates(
        scope, namespace, generation_id, seed_node_ids, relation_types, max_hops
    )
    found = GraphCandidateSet.model_validate_json(found.model_dump_json())
    event_ids = {str(candidate.event_id) for candidate in found.candidates}
    rows: Sequence[RowMapping] = ()
    if event_ids:
        rows = (
            session.execute(
                select(
                    graph_projection_state,
                    graph_projection_batches.c.batch_id.label("trusted_batch_id"),
                    graph_projection_batches.c.sequence.label("trusted_sequence"),
                    graph_projection_batches.c.payload_sha256.label("trusted_digest"),
                    graph_projection_batches.c.kind.label("trusted_kind"),
                )
                .select_from(
                    graph_projection_state.join(
                        graph_projection_batches,
                        and_(
                            graph_projection_batches.c.batch_id
                            == graph_projection_state.c.body["batch_id"].astext,
                            graph_projection_batches.c.namespace
                            == graph_projection_state.c.namespace,
                            graph_projection_batches.c.partition_key
                            == graph_projection_state.c.partition_key,
                            graph_projection_batches.c.generation_id
                            == graph_projection_state.c.generation_id,
                            graph_projection_batches.c.event_id
                            == graph_projection_state.c.event_id,
                        ),
                    )
                )
                .where(
                    graph_projection_state.c.namespace == namespace,
                    graph_projection_state.c.partition_key == partition,
                    graph_projection_state.c.generation_id == str(generation_id),
                    graph_projection_state.c.state_kind == "slot",
                    graph_projection_state.c.event_id.in_(event_ids),
                )
                .limit(401)
            )
            .mappings()
            .all()
        )
    slots: dict[UUID, tuple[ProjectionSlot, RowMapping]] = {}
    for row in rows:
        try:
            slot = _body(ProjectionSlot, row)
        except ValidationError:
            raise ProjectionDigestConflict("graph_projection_ack_invalid") from None
        if (
            slot.event_id in slots
            or str(slot.event_id) != row["event_id"]
            or row["state_key"] != "event:" + str(slot.event_id)
        ):
            raise ProjectionDigestConflict("graph_projection_ack_identity_invalid")
        slots[slot.event_id] = slot, row
    for candidate in found.candidates:
        if candidate.event_id not in slots:
            raise ProjectionNotReady("graph_projection_candidate_unacknowledged")
        slot, row = slots[candidate.event_id]
        if (
            slot.acknowledged_sequence != candidate.sequence
            or slot.captured_sequence != candidate.sequence
            or row["trusted_sequence"] != candidate.sequence
            or str(slot.batch_id) != row["trusted_batch_id"]
            or slot.acknowledged_sha256 != candidate.payload_sha256
            or slot.payload_sha256 != candidate.payload_sha256
            or row["trusted_digest"] != candidate.payload_sha256
            or row["trusted_kind"] != "snapshot"
        ):
            raise ProjectionDigestConflict("graph_projection_candidate_ack_disagrees")
    current = _body(
        ReconciliationManifest,
        _state_row(session, namespace, partition, generation_id, "partition"),
    )
    if current != manifest or _epochs(session, scope) != manifest.scope_epochs:
        raise ProjectionNotReady("graph_projection_not_current")
    return found


def list_projection_history(
    session: Session,
    scope: AccessScope,
    namespace: str,
    event_id: UUID,
    *,
    limit: int = 20,
    after: tuple[datetime, UUID] | None = None,
) -> tuple[ProjectionHistoryEntry, ...]:
    """Scoped metadata only, bounded stable pagination; never load private batch content."""
    if type(event_id) is not UUID or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("projection history outside bounds")
    fields = (
        "batch_id",
        "generation_id",
        "event_id",
        "sequence",
        "kind",
        "captured_at",
        "payload_sha256",
    )
    query = select(*(graph_projection_batches.c[key] for key in fields)).where(
        graph_projection_batches.c.namespace == namespace,
        graph_projection_batches.c.partition_key == partition_for_scope(scope),
        graph_projection_batches.c.event_id == str(event_id),
    )
    if after is not None:
        timestamp, identifier = after
        if timestamp.tzinfo is None or type(identifier) is not UUID:
            raise ValueError("invalid projection history cursor")
        query = query.where(
            tuple_(graph_projection_batches.c.captured_at, graph_projection_batches.c.batch_id)
            > (timestamp, str(identifier))
        )
    query = query.order_by(
        graph_projection_batches.c.captured_at, graph_projection_batches.c.batch_id
    ).limit(limit)
    return tuple(
        ProjectionHistoryEntry.model_validate_json(
            json.dumps(
                dict(row),
                default=lambda value: (
                    value.isoformat() if isinstance(value, datetime) else str(value)
                ),
            )
        )
        for row in session.execute(query).mappings()
    )


TaskScopeAuthorizer = Callable[[Session, JobExecutionContext], AccessScope]


def build_graph_apply_handler(
    store: GraphProjectionStore,
    authorize: TaskScopeAuthorizer,
) -> JobHandler:
    """Root-owned worker registration supplies the authenticated task scope provider."""

    class BatchRequest(ProjectionRecord):
        batch_id: UUID

    def handle(
        session: Session, context: JobExecutionContext, payload: bytes
    ) -> JobExecutionResult:
        request = BatchRequest.model_validate_json(payload)
        try:
            scope = authorize(session, context)
            partition = partition_for_scope(scope)
            if context.tenant_id != (scope.tenant_id if partition != "public" else None):
                raise PermissionDeniedError("graph job scope denied")
            receipt = apply_projection_batch(
                session, scope, request.batch_id, store, datetime.now(UTC)
            )
        except (PermissionDeniedError, CrossTenantAccessError):
            raise JobExecutionError("graph_projection_scope_denied", blocked=True) from None
        except ProjectionDigestConflict:
            raise JobExecutionError("graph_projection_digest_conflict", blocked=True) from None
        except ProjectionCapacityError:
            raise JobExecutionError("graph_projection_capacity_exceeded", blocked=True) from None
        except ProjectionNotReady:
            raise JobExecutionError("graph_projection_state_unavailable", blocked=True) from None
        return JobExecutionResult(result_ref="pg:graph_batch:" + str(receipt.batch_id))

    return handle
