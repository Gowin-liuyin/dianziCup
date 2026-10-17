"""Public task identity and typed result locators in the caller's PostgreSQL transaction.

JobRun remains the sole status and lease authority. Trusted result readers must lock
and revalidate the actual published answer and current evidence in this same Session;
they must never generate an answer, debit quota or open another transaction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Table,
    Text,
    column,
    event,
    func,
    insert,
    select,
    table,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.orm import ORMExecuteState, Session, SessionTransaction

from ai_intel.api.actor_references import (
    ActorReference,
    actor_reference_from_payload,
    actor_reference_payload,
    lock_actor_reference_scope,
)
from ai_intel.api.public_extension_reads import PublicReadUnavailable
from ai_intel.api.public_write_adapters import parse_public_ask_request
from ai_intel.api.question_contracts import QuestionAnswerResponse, QuestionRequest
from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.knowledge.models import job_runs, metadata
from ai_intel.workers.jobs import JobLeaseLostError, require_job_lease

SCHEMA_VERSION = "r18-public-task-binding-1"
TaskType = Literal["ask", "stack_check"]
ResultKind = Literal["qa_answer", "stack_check"]
JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
PENDING_STATUSES = frozenset({"queued", "running", "retry_wait", "waiting_approval"})
ERROR_STATUSES = frozenset({"failed", "cancelled", "blocked"})

public_task_bindings = Table(
    "public_task_bindings",
    metadata,
    Column("task_id", Text, ForeignKey("job_runs.job_id"), primary_key=True),
    Column("schema_version", Text, nullable=False),
    Column("task_type", Text, nullable=False),
    Column("owner_user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("tenant_id", Text),
    Column("authorized_role", Text, nullable=False),
    Column("actor_reference", JSONB, nullable=False),
    Column("public_request_json", JSONB, nullable=False),
    Column("request_sha256", Text, nullable=False),
    Column("trace_id", Text, nullable=False),
    Column("admitted_at", DateTime(timezone=True), nullable=False),
    Column("deadline_at", DateTime(timezone=True), nullable=False),
    Column("result_kind", Text),
    Column("result_id", Text),
    Column("result_published_at", DateTime(timezone=True)),
    CheckConstraint(f"schema_version = '{SCHEMA_VERSION}'", name="ck_public_task_schema"),
    CheckConstraint("task_type IN ('ask','stack_check')", name="ck_public_task_type"),
    CheckConstraint(
        "authorized_role IN ('tenant_admin','system_admin','analyst','viewer')",
        name="ck_public_task_role",
    ),
    CheckConstraint("jsonb_typeof(actor_reference) = 'object'", name="ck_public_task_actor"),
    CheckConstraint("jsonb_typeof(public_request_json) = 'object'", name="ck_public_task_request"),
    CheckConstraint("request_sha256 ~ '^[0-9a-f]{64}$'", name="ck_public_task_digest"),
    CheckConstraint(
        "trace_id ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'",
        name="ck_public_task_trace",
    ),
    CheckConstraint("deadline_at > admitted_at", name="ck_public_task_deadline"),
    CheckConstraint(
        "(result_kind IS NULL AND result_id IS NULL AND result_published_at IS NULL) OR "
        "(result_kind IS NOT NULL AND result_id IS NOT NULL AND result_published_at IS NOT NULL "
        "AND ((task_type = 'ask' AND result_kind = 'qa_answer') OR "
        "(task_type = 'stack_check' AND result_kind = 'stack_check')) "
        "AND result_published_at >= admitted_at AND result_published_at < deadline_at)",
        name="ck_public_task_result",
    ),
    CheckConstraint(
        "result_id IS NULL OR result_id ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'",
        name="ck_public_task_result_id",
    ),
)

PUBLIC_TASK_IMMUTABILITY_SQL = """
CREATE FUNCTION protect_public_task_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE'
 OR (to_jsonb(NEW) - ARRAY['result_kind','result_id','result_published_at']) <>
    (to_jsonb(OLD) - ARRAY['result_kind','result_id','result_published_at'])
 OR OLD.result_kind IS NOT NULL
 OR NEW.result_kind IS NULL THEN
  RAISE EXCEPTION 'public task binding is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER public_task_bindings_immutable BEFORE UPDATE OR DELETE ON public_task_bindings
FOR EACH ROW EXECUTE FUNCTION protect_public_task_binding();
"""

workflow_owners = table(
    "investigation_workflows",
    column("job_id", Text),
    column("owner_user_id", Text),
    column("tenant_id", Text),
    column("authorized_role", Text),
    column("actor_reference", JSONB),
    column("input_json", JSONB),
    column("deadline_at", DateTime(timezone=True)),
)
workflow_operations = table(
    "investigation_operations",
    column("job_id", Text),
    column("kind", Text),
    column("role", Text),
    column("status", Text),
)


class PublicTaskIntegrityError(PublicReadUnavailable):
    """The PG task cannot be faithfully projected; never emit completed with no result."""


class UnsupportedPublicTaskError(PublicReadUnavailable):
    """No actual owned stack async producer has been frozen and installed."""


class PublicTaskBindingConflict(ValueError):
    """An existing job cannot be rebound to another public request or result."""


@dataclass(frozen=True, slots=True)
class PublicTaskBindingReceipt:
    task_id: UUID
    created: bool
    trace_id: UUID
    admitted_at: datetime


class PublicTaskResultReader(Protocol):
    """Fixed trusted PG read ports, never supplied by request bodies or model tools."""

    def read_qa_answer_in_session(
        self,
        session: Session,
        scope: AccessScope,
        answer_id: UUID,
        *,
        task_id: UUID,
        request_sha256: str,
    ) -> QuestionAnswerResponse:
        """Read actual published owner/request-bound QA with locked current support proof."""
        ...

    def read_stack_check_in_session(
        self,
        session: Session,
        scope: AccessScope,
        result_id: UUID,
        *,
        task_id: UUID,
        request_sha256: str,
    ) -> dict[str, JsonValue]:
        """Reserved fixed port; this version rejects stack tasks before calling it."""
        ...


def _aware(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PublicTaskIntegrityError("public_task_timestamp_invalid")
    return value.astimezone(UTC)


def _json_object(value: object) -> dict[str, JsonValue]:
    try:
        return JSON_OBJECT.validate_python(value, strict=True)
    except ValidationError:
        raise PublicTaskIntegrityError("public_task_payload_invalid") from None


def public_request_digest(request: QuestionRequest) -> tuple[dict[str, JsonValue], str]:
    """Canonicalize strict public business fields; credentials and body identity are rejected."""
    payload = _json_object(request.model_dump(mode="json", exclude_unset=True))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return payload, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_workflow_request(request: QuestionRequest, stored_input: object) -> None:
    """A single-event investigation cannot silently stand in for a broader public request."""
    payload = _json_object(stored_input)
    original = _json_object(payload.get("request"))
    if (
        request.conversation_id is not None
        or request.known_at is not None
        or request.valid_at is not None
        or len(request.event_ids) != 1
        or len(request.asset_ids) > 1
        or request.question != original.get("question")
        or str(request.event_ids[0]) != original.get("event_id")
        or [str(item) for item in request.asset_ids]
        != ([original["asset_id"]] if original.get("asset_id") is not None else [])
    ):
        raise UnsupportedPublicTaskError("public_task_request_scope_unsupported")


def project_workflow_steps(
    rows: list[Mapping[str, object]] | list[RowMapping],
) -> tuple[list[str], list[str], list[str]]:
    """Group only persisted receipts; retries do not count the same role as both done and failed."""
    states: dict[str, set[str]] = {}
    for row in rows:
        kind, role, status = row["kind"], row["role"], row["status"]
        if (
            not isinstance(kind, str)
            or not isinstance(role, str)
            or not isinstance(status, str)
            or kind not in {"node", "tool", "model"}
            or role not in {item.value for item in AgentRole}
            or status not in {"reserved", "succeeded", "partial", "failed"}
        ):
            raise PublicTaskIntegrityError("public_task_operation_invalid")
        states.setdefault(f"{kind}:{role}", set()).add(str(status))
    completed, pending, failed = [], [], []
    for label, outcomes in sorted(states.items()):
        if "failed" in outcomes:
            failed.append(label)
        elif outcomes & {"reserved", "partial"}:
            pending.append(label)
        else:
            completed.append(label)
    return completed, pending, failed


def _problem(status: str, trace_id: str) -> dict[str, JsonValue]:
    return {
        "type": "urn:dianzi:problem:public-task",
        "title": "Public task could not complete",
        "status": 503 if status == "blocked" else 409,
        "error": "public_task_" + status,
        "trace_id": trace_id,
    }


class PublicTaskBindingService:
    """Coordinate typed bindings while callers retain admission and completion ownership."""

    def __init__(
        self, engine: Engine, *, result_reader: PublicTaskResultReader | None = None
    ) -> None:
        self.engine = engine
        self.result_reader = result_reader

    def _connection(self, session: Session) -> Connection:
        if not session.in_transaction():
            raise ValueError("public task requires the caller transaction")
        bind = session.get_bind()
        if (
            bind is not self.engine
            and not (isinstance(bind, Connection) and bind.engine is self.engine)
        ) or any(
            session.get_bind(clause=stored_table) is not bind
            for stored_table in metadata.tables.values()
        ):
            raise ValueError("public task requires the service engine")
        connection = session.connection()
        if connection.engine is not self.engine:
            raise ValueError("public task requires the service engine and connection")
        if not connection.in_transaction():
            raise ValueError("public task requires the caller transaction")
        return connection

    @contextmanager
    def _session_fence(self, session: Session) -> Iterator[None]:
        """Reject statement routing or transaction changes during these fixed trusted ports."""
        connection = self._connection(session)
        session_transaction = session.get_transaction()
        connection_transaction = connection.get_transaction()

        def verify_transaction() -> None:
            if (
                session.get_transaction() is not session_transaction
                or connection.get_transaction() is not connection_transaction
            ):
                raise PublicTaskIntegrityError("public_task_result_transaction_changed")

        def verify_statement(state: ORMExecuteState) -> None:
            verify_transaction()
            resolved = session.get_bind(**state.bind_arguments)
            if resolved is not self.engine and resolved is not connection:
                raise ValueError("public task requires the service engine and connection")
            actual = session.connection(bind_arguments=dict(state.bind_arguments))
            if actual is not connection:
                raise ValueError("public task requires the service engine and connection")

        def verify_connection(
            current: Session, transaction: SessionTransaction, actual: Connection
        ) -> None:
            verify_transaction()
            if actual is not connection:
                raise ValueError("public task requires the service engine and connection")

        event.listen(session, "do_orm_execute", verify_statement)
        event.listen(session, "after_begin", verify_connection)
        try:
            yield
            verify_transaction()
        finally:
            event.remove(session, "after_begin", verify_connection)
            event.remove(session, "do_orm_execute", verify_statement)

    @staticmethod
    def _now(connection: Connection) -> datetime:
        return _aware(connection.scalar(select(func.clock_timestamp())))

    def _lock_job(
        self, session: Session, actor: ActorReference, task_id: UUID
    ) -> tuple[Connection, AccessScope, RowMapping]:
        connection = self._connection(session)
        scope = lock_actor_reference_scope(connection, actor, self._now(connection))
        scope.requires(READ_PUBLIC)
        row = (
            session.execute(
                select(job_runs).where(job_runs.c.job_id == str(task_id)).with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None or row["tenant_id"] != scope.tenant_id:
            raise CrossTenantAccessError("resource not found")
        return connection, scope, row

    @staticmethod
    def _owner_matches(
        row: Mapping[str, object] | RowMapping, actor: ActorReference
    ) -> ActorReference:
        stored = actor_reference_from_payload(_json_object(row["actor_reference"]))
        stored_payload = actor_reference_payload(stored)
        current_payload = actor_reference_payload(actor)
        stored_payload.pop("created_at")
        current_payload.pop("created_at")
        if (
            row["owner_user_id"] != actor.user_id
            or row["tenant_id"] != actor.tenant_id
            or row["authorized_role"] != actor.role.value
            or stored_payload != current_payload
        ):
            raise CrossTenantAccessError("resource not found")
        return stored

    def _locked_binding(
        self, session: Session, actor: ActorReference, task_id: UUID
    ) -> tuple[Connection, AccessScope, RowMapping, RowMapping]:
        connection, scope, job = self._lock_job(session, actor, task_id)
        binding = (
            session.execute(
                select(public_task_bindings)
                .where(public_task_bindings.c.task_id == str(task_id))
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if binding is None:
            raise CrossTenantAccessError("resource not found")
        original_actor = self._owner_matches(binding, actor)
        if binding["task_type"] != "ask":
            raise UnsupportedPublicTaskError("public_stack_task_unsupported")
        if job["job_type"] != "investigation" or binding["schema_version"] != SCHEMA_VERSION:
            raise PublicTaskIntegrityError("public_task_job_binding_invalid")
        owner = self._lock_workflow(session, actor, task_id)
        if actor_reference_from_payload(owner["actor_reference"]) != original_actor:
            raise PublicTaskIntegrityError("public_task_actor_binding_invalid")
        request = parse_public_ask_request(
            json.dumps(_json_object(binding["public_request_json"]), ensure_ascii=False).encode()
        )
        _, digest = public_request_digest(request)
        if digest != binding["request_sha256"]:
            raise PublicTaskIntegrityError("public_task_request_digest_invalid")
        validate_workflow_request(request, owner["input_json"])
        if request.asset_ids:
            scope.requires(READ_ASSET)
        lock_actor_reference_scope(connection, original_actor, self._now(connection))
        return connection, scope, job, binding

    def _lock_workflow(self, session: Session, actor: ActorReference, task_id: UUID) -> RowMapping:
        owner = (
            session.execute(
                select(workflow_owners)
                .where(workflow_owners.c.job_id == str(task_id))
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if owner is None:
            raise CrossTenantAccessError("resource not found")
        self._owner_matches(owner, actor)
        return owner

    def bind_in_session(
        self,
        session: Session,
        *,
        job_id: UUID,
        actor: ActorReference,
        task_type: TaskType,
        public_request: bytes,
        deadline_at: datetime,
    ) -> PublicTaskBindingReceipt:
        """Bind actual admission atomically with caller enqueue/quota; replay retains trace/time."""
        with self._session_fence(session):
            if task_type != "ask":
                raise UnsupportedPublicTaskError("public_stack_task_unsupported")
            request = parse_public_ask_request(public_request)
            payload, digest = public_request_digest(request)
            deadline = _aware(deadline_at)
            connection, scope, job = self._lock_job(session, actor, job_id)
            if job["job_type"] != "investigation":
                raise PublicTaskIntegrityError("public_task_job_type_invalid")
            owner = self._lock_workflow(session, actor, job_id)
            original_actor = actor_reference_from_payload(owner["actor_reference"])
            validate_workflow_request(request, owner["input_json"])
            if request.asset_ids:
                scope.requires(READ_ASSET)
            existing = (
                session.execute(
                    select(public_task_bindings)
                    .where(public_task_bindings.c.task_id == str(job_id))
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if existing is not None:
                self._owner_matches(existing, actor)
                if existing["task_type"] != task_type or existing["request_sha256"] != digest:
                    raise PublicTaskBindingConflict("public_task_request_conflict")
                lock_actor_reference_scope(connection, actor, self._now(connection))
                return PublicTaskBindingReceipt(
                    job_id, False, UUID(existing["trace_id"]), _aware(existing["admitted_at"])
                )
            now = self._now(connection)
            lock_actor_reference_scope(connection, actor, now)
            admitted_at = _aware(job["created_at"])
            if (
                job["status"] != "queued"
                or now < admitted_at
                or deadline <= now
                or deadline > _aware(owner["deadline_at"])
            ):
                raise PublicTaskIntegrityError("public_task_admission_invalid")
            trace_id = uuid4()
            session.execute(
                insert(public_task_bindings).values(
                    task_id=str(job_id),
                    schema_version=SCHEMA_VERSION,
                    task_type=task_type,
                    owner_user_id=actor.user_id,
                    tenant_id=actor.tenant_id,
                    authorized_role=actor.role.value,
                    actor_reference=actor_reference_payload(original_actor),
                    public_request_json=payload,
                    request_sha256=digest,
                    trace_id=str(trace_id),
                    admitted_at=admitted_at,
                    deadline_at=deadline,
                )
            )
            lock_actor_reference_scope(connection, actor, self._now(connection))
            return PublicTaskBindingReceipt(job_id, True, trace_id, admitted_at)

    def _read_result(
        self,
        session: Session,
        scope: AccessScope,
        binding: Mapping[str, object] | RowMapping,
        *,
        publishing: bool = False,
    ) -> tuple[QuestionAnswerResponse, datetime]:
        if self.result_reader is None:
            raise PublicReadUnavailable("public_task_result_reader_not_configured")
        if binding["result_kind"] != "qa_answer":
            raise PublicTaskIntegrityError("public_task_result_type_invalid")
        answer_id = UUID(str(binding["result_id"]))
        connection = self._connection(session)
        answer = self.result_reader.read_qa_answer_in_session(
            session,
            scope,
            answer_id,
            task_id=UUID(str(binding["task_id"])),
            request_sha256=str(binding["request_sha256"]),
        )
        if not isinstance(answer, QuestionAnswerResponse):
            raise PublicTaskIntegrityError("public_task_answer_type_invalid")
        if self._connection(session) is not connection:
            raise PublicTaskIntegrityError("public_task_result_transaction_changed")
        try:
            validated = QuestionAnswerResponse.model_validate_json(answer.model_dump_json())
        except ValidationError:
            raise PublicTaskIntegrityError("public_task_answer_invalid") from None
        admitted_at = _aware(binding["admitted_at"])
        publication = (
            validated.completed_at if publishing else _aware(binding["result_published_at"])
        )
        elapsed_ms = int((validated.completed_at - admitted_at).total_seconds() * 1000)
        now = self._now(connection)
        if (
            validated.answer_id != answer_id
            or validated.freshness.value != "current"
            or validated.started_at != admitted_at
            or validated.completed_at != publication
            or publication > now
            or validated.latency_milliseconds != elapsed_ms
        ):
            raise PublicTaskIntegrityError("public_task_answer_binding_invalid")
        return validated, now

    def publish_result_in_session(
        self,
        session: Session,
        *,
        task_id: UUID,
        actor: ActorReference,
        worker_id: str,
        expected_attempt: int,
        result_kind: ResultKind,
        result_id: UUID,
    ) -> None:
        """CAS a verified locator under lease; caller completes JobRun in the same commit."""
        with self._session_fence(session):
            connection, scope, _, binding = self._locked_binding(session, actor, task_id)
            if result_kind != "qa_answer":
                raise PublicTaskIntegrityError("public_task_result_type_invalid")
            now = self._now(connection)
            lock_actor_reference_scope(connection, actor, now)
            require_job_lease(
                session, str(task_id), worker_id, now, expected_attempt=expected_attempt
            )
            if now >= _aware(binding["deadline_at"]):
                raise JobLeaseLostError("public task deadline expired")
            replaying = binding["result_kind"] is not None
            if replaying:
                if binding["result_kind"] != result_kind or binding["result_id"] != str(result_id):
                    raise PublicTaskBindingConflict("public_task_result_conflict")
                answer, final_now = self._read_result(session, scope, binding)
            else:
                candidate = dict(binding, result_kind=result_kind, result_id=str(result_id))
                answer, final_now = self._read_result(session, scope, candidate, publishing=True)
            lock_actor_reference_scope(connection, actor, final_now)
            require_job_lease(
                session, str(task_id), worker_id, final_now, expected_attempt=expected_attempt
            )
            if final_now >= _aware(binding["deadline_at"]):
                raise JobLeaseLostError("public task deadline expired")
            if replaying:
                return
            changed = session.execute(
                update(public_task_bindings)
                .where(
                    public_task_bindings.c.task_id == str(task_id),
                    public_task_bindings.c.result_kind.is_(None),
                )
                .values(
                    result_kind=result_kind,
                    result_id=str(result_id),
                    result_published_at=answer.completed_at,
                )
                .returning(public_task_bindings.c.task_id)
            ).scalar_one_or_none()
            if changed != str(task_id):
                raise PublicTaskBindingConflict("public_task_result_conflict")

    def read_in_session(
        self, session: Session, *, task_id: UUID, actor: ActorReference
    ) -> dict[str, JsonValue]:
        """Project PG status and actual receipts; polling has no model or quota side effects."""
        with self._session_fence(session):
            connection, scope, job, binding = self._locked_binding(session, actor, task_id)
            status = job["status"]
            rows = (
                session.execute(
                    select(workflow_operations).where(workflow_operations.c.job_id == str(task_id))
                )
                .mappings()
                .all()
            )
            completed, pending, failed = project_workflow_steps(list(rows))
            result: dict[str, JsonValue] | None = None
            error: dict[str, JsonValue] | None = None
            if status in PENDING_STATUSES:
                if binding["result_kind"] is not None:
                    raise PublicTaskIntegrityError("public_task_pending_has_result")
            elif status == "succeeded":
                if binding["result_kind"] is None or pending or failed:
                    raise PublicTaskIntegrityError("public_task_succeeded_without_result")
                answer, _ = self._read_result(session, scope, binding)
                result = _json_object(answer.model_dump(mode="json"))
            elif status == "partial":
                if binding["result_kind"] is not None:
                    answer, _ = self._read_result(session, scope, binding)
                    result = _json_object(answer.model_dump(mode="json"))
            elif status in ERROR_STATUSES:
                error = _problem(status, str(binding["trace_id"]))
            else:
                raise PublicTaskIntegrityError("public_task_status_invalid")
            lock_actor_reference_scope(connection, actor, self._now(connection))
            created, updated = _aware(job["created_at"]), _aware(job["updated_at"])
            if updated < created or created != _aware(binding["admitted_at"]):
                raise PublicTaskIntegrityError("public_task_time_binding_invalid")
            return _json_object(
                {
                    "task": {
                        "task_id": str(task_id),
                        "task_type": "ask",
                        "status": str(status),
                        "poll_uri": "/api/v1/tasks/" + str(task_id),
                        "created_at": created.isoformat(),
                        "updated_at": updated.isoformat(),
                    },
                    "result": result,
                    "error": error,
                    "completed_steps": completed,
                    "pending_steps": pending,
                    "failed_steps": failed,
                }
            )
