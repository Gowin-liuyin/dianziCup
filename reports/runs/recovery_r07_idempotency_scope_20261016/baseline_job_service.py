"""Durable, bounded enrichment uses PG jobs for state and one final atomic publication."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.document_read_service import sources
from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    PERMISSION_VERSION,
    READ_ASSET,
    READ_PUBLIC,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
    Role,
)
from ai_intel.domain.enums import DimensionStatus
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.contracts import DimensionAttempt
from ai_intel.enrichment.field_sources import FieldEvidenceError
from ai_intel.enrichment.inputs import (
    EnrichmentInputError,
    LoadedEnrichmentInputs,
    _require_input_scopes,
    load_event_enrichment_inputs,
)
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy, EventEnrichmentRequest
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_types import (
    MODEL_DIMENSIONS,
    TERMINAL_STATUSES,
    DocumentSnapshot,
    EnrichmentDimensionView,
    EnrichmentEnqueueReceipt,
    EnrichmentJobPayload,
    EnrichmentStepView,
    EnrichmentWorkflowView,
    ExposureStepClient,
    FrozenEnrichmentInputs,
    ModelCallState,
    ParentScopeSnapshot,
    combine_exposure_attempts,
    json_payload,
    logical_job_status,
    physical_steps,
)
from ai_intel.enrichment.model_fields import extract_model_dimension
from ai_intel.enrichment.publication import (
    EnrichmentPublicationError,
    _lock_input_parents,
    _require_current_inputs,
    publish_enrichment_attempts,
)
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.models.generation import AttemptMetadata, GenerationClient
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.event_linking import EventRepository
from ai_intel.knowledge.models import document_revisions, documents, job_runs, users
from ai_intel.knowledge.persistence_models import events
from ai_intel.workers.executor import (
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
    utc_now,
)
from ai_intel.workers.jobs import require_aware_time

ENRICHMENT_PARENT_JOB_TYPE = "initialize_event_enrichment"
ENRICHMENT_STEP_JOB_TYPE = "execute_event_enrichment_step"
ENRICHMENT_PUBLICATION_JOB_TYPE = "publish_event_enrichment"
RULE_VERSION = "r07-enrichment-workflow-1"
MODEL_TRACE_ADAPTER = TypeAdapter(tuple[AttemptMetadata, ...])


class EnrichmentWorkflowError(ValueError):
    """Fixed safe codes distinguish stale inputs and invalid workflow references."""

    def __init__(self, code: str, status: int = 409) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", code) or status not in {403, 404, 409, 503}:
            raise ValueError("invalid enrichment workflow error")
        super().__init__(code)
        self.code = code
        self.status = status


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _authenticated_scope(
    session: Session,
    session_hash: str,
    at: datetime,
    *,
    lock: bool = False,
) -> AccessScope:
    require_aware_time(at)
    if not re.fullmatch(r"[0-9a-f]{64}", session_hash):
        raise PermissionDeniedError("enrichment_session_invalid")
    query = (
        select(auth_sessions.c.user_id, users.c.tenant_id, users.c.role)
        .select_from(auth_sessions.join(users))
        .where(
            auth_sessions.c.session_hash == session_hash,
            auth_sessions.c.revoked_at.is_(None),
            auth_sessions.c.expires_at > at,
        )
    )
    if lock:
        query = query.with_for_update(read=True, of=(auth_sessions, users))
    row = session.execute(query).mappings().first()
    if row is None:
        raise PermissionDeniedError("enrichment_session_invalid")
    return AccessScope.for_authenticated_user(row["user_id"], row["tenant_id"], Role(row["role"]))


def _write_permission(visibility: str) -> str:
    return MANAGE_PUBLIC_SOURCES if visibility == "public" else WRITE_ASSET


def _parent_snapshots(
    session: Session, loaded: LoadedEnrichmentInputs
) -> tuple[ParentScopeSnapshot, ...]:
    rows = session.execute(
        select(
            document_revisions.c.revision_id,
            documents.c.document_id,
            documents.c.source_id,
            document_revisions.c.visibility.label("revision_visibility"),
            document_revisions.c.tenant_id.label("revision_tenant_id"),
            documents.c.visibility.label("document_visibility"),
            documents.c.tenant_id.label("document_tenant_id"),
            sources.c.visibility.label("source_visibility"),
            sources.c.tenant_id.label("source_tenant_id"),
            sources.c.category.label("source_category"),
        )
        .join(documents, documents.c.document_id == document_revisions.c.document_id)
        .join(sources, sources.c.source_id == documents.c.source_id)
        .where(document_revisions.c.revision_id.in_(tuple(map(str, loaded.context.revision_ids))))
        .order_by(document_revisions.c.revision_id)
    ).mappings()
    return tuple(ParentScopeSnapshot.model_validate(dict(row)) for row in rows)


def _freeze_inputs(session: Session, loaded: LoadedEnrichmentInputs) -> FrozenEnrichmentInputs:
    return FrozenEnrichmentInputs(
        context=loaded.context,
        scope=loaded.scope,
        documents=tuple(
            DocumentSnapshot.model_validate(document.model_dump()) for document in loaded.documents
        ),
        parents=_parent_snapshots(session, loaded),
    )


def _binding(row: RowMapping | dict[str, object]) -> dict[str, object]:
    return {
        key: row[key]
        for key in (
            "event_id",
            "actor_user_id",
            "actor_session_hash",
            "actor_tenant_id",
            "actor_role",
            "actor_permission_version",
            "request_sha256",
            "execution_policy_sha256",
            "rule_version",
        )
    }


def _attempt_outcome(attempt: DimensionAttempt) -> JobExecutionResult:
    if attempt.status == DimensionStatus.BLOCKED:
        return JobExecutionResult("blocked", error_code=attempt.error_code)
    if attempt.status == DimensionStatus.FAILED:
        return JobExecutionResult("failed", error_code=attempt.error_code)
    if attempt.status in {
        DimensionStatus.PENDING,
        DimensionStatus.NOT_FOUND,
        DimensionStatus.CONFLICT,
    }:
        return JobExecutionResult("partial", error_code=attempt.error_code)
    return JobExecutionResult()


class EnrichmentJobService:
    """Caller owns the business transaction; only model reservations and receipts commit alone."""

    def __init__(
        self,
        engine: Engine,
        store: ContentStorage,
        *,
        execution_policy: Callable[[], EnrichmentExecutionPolicy],
        generation_client_factory: Callable[[], GenerationClient | None] | None = None,
        exposure_client: ExposureStepClient | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.engine = engine
        self.store = store
        self.execution_policy = execution_policy
        self.generation_client_factory = generation_client_factory
        self.exposure_client = exposure_client
        self.clock = clock

    def enqueue(
        self,
        session: Session,
        scope: AccessScope,
        event_id: UUID,
        request: EventEnrichmentRequest,
        *,
        actor_session_hash: str,
        idempotency_key: str,
        created_at: datetime,
    ) -> EnrichmentEnqueueReceipt:
        require_aware_time(created_at)
        request = EventEnrichmentRequest.model_validate_json(request.model_dump_json())
        current = _authenticated_scope(session, actor_session_hash, created_at, lock=True)
        if current != scope:
            raise PermissionDeniedError("enrichment_authorization_changed")
        revision_ids = EventRepository(session, current).get_source_revisions(str(event_id))
        event = (
            session.execute(select(events).where(events.c.event_id == str(event_id)))
            .mappings()
            .one()
        )
        current.requires(_write_permission(event["visibility"]))
        if not 1 <= len(revision_ids) <= 20:
            raise EnrichmentWorkflowError("active_bounded_event_revisions_required")
        _require_input_scopes(
            session,
            current,
            VisibilityScope(visibility=event["visibility"], tenant_id=event["tenant_id"]),
            revision_ids,
        )
        policy = EnrichmentExecutionPolicy.model_validate_json(
            self.execution_policy().model_dump_json()
        )
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ValueError("invalid idempotency key")
        workflow_id = uuid5(
            NAMESPACE_URL, "ai-intel:enrichment:" + repr((event["tenant_id"], idempotency_key))
        )
        binding: dict[str, object] = {
            "event_id": str(event_id),
            "actor_user_id": current.user_id,
            "actor_session_hash": actor_session_hash,
            "actor_tenant_id": current.tenant_id,
            "actor_role": current.role.value,
            "actor_permission_version": current.permission_version,
            "request_sha256": _digest(request.model_dump(mode="json")),
            "execution_policy_sha256": _digest(policy.model_dump(mode="json")),
            "rule_version": RULE_VERSION,
        }
        parent_id = enqueue_job(
            session,
            event["tenant_id"],
            ENRICHMENT_PARENT_JOB_TYPE,
            json_payload(
                EnrichmentJobPayload(workflow_id=workflow_id, binding_sha256=_digest(binding))
            ),
            created_at,
            idempotency_key=idempotency_key,
            max_attempts=3,
        )
        existing = session.execute(
            select(enrichment_workflows.c.workflow_id).where(
                enrichment_workflows.c.parent_job_id == parent_id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return EnrichmentEnqueueReceipt(UUID(existing), UUID(parent_id), True)
        if (
            event["status"] != "active"
            or event["business_version"] != request.expected_event_version
        ):
            raise EnrichmentWorkflowError("enrichment_event_version_changed")
        session.execute(
            insert(enrichment_workflows).values(
                **binding,
                workflow_id=str(workflow_id),
                parent_job_id=parent_id,
                request_payload=request.model_dump(mode="json"),
                execution_policy=policy.model_dump(mode="json"),
                visibility=event["visibility"],
                tenant_id=event["tenant_id"],
                created_at=created_at,
            )
        )
        return EnrichmentEnqueueReceipt(workflow_id, UUID(parent_id), False)

    def _workflow(
        self,
        session: Session,
        context: JobExecutionContext,
        payload: bytes,
    ) -> tuple[RowMapping, EnrichmentJobPayload, AccessScope]:
        request = EnrichmentJobPayload.model_validate_json(payload)
        row = (
            session.execute(
                select(enrichment_workflows).where(
                    enrichment_workflows.c.workflow_id == str(request.workflow_id)
                )
            )
            .mappings()
            .first()
        )
        if (
            row is None
            or row["tenant_id"] != context.tenant_id
            or _digest(_binding(row)) != request.binding_sha256
            or _digest(row["request_payload"]) != row["request_sha256"]
        ):
            raise JobExecutionError("enrichment_workflow_binding_invalid", blocked=True)
        scope = self._execution_scope(session, row)
        return row, request, scope

    def _execution_scope(
        self, session: Session, row: RowMapping, *, lock: bool = False
    ) -> AccessScope:
        try:
            scope = _authenticated_scope(
                session, row["actor_session_hash"], self.clock(), lock=lock
            )
            if (
                scope.user_id != row["actor_user_id"]
                or scope.tenant_id != row["actor_tenant_id"]
                or scope.role.value != row["actor_role"]
                or scope.permission_version != row["actor_permission_version"]
                or row["actor_permission_version"] != PERMISSION_VERSION
            ):
                raise PermissionDeniedError("enrichment_authorization_changed")
            scope.enforce_visible(row["visibility"], row["tenant_id"])
            scope.requires(_write_permission(row["visibility"]))
        except PermissionError:
            raise JobExecutionError("enrichment_authorization_changed", blocked=True) from None
        policy = self.execution_policy()
        if (
            _digest(policy.model_dump(mode="json")) != row["execution_policy_sha256"]
            or _digest(row["execution_policy"]) != row["execution_policy_sha256"]
        ):
            raise JobExecutionError("enrichment_execution_policy_changed", blocked=True)
        return scope

    def _current_inputs(
        self, session: Session, row: RowMapping, scope: AccessScope
    ) -> FrozenEnrichmentInputs:
        try:
            saved = FrozenEnrichmentInputs.model_validate_json(json.dumps(row["input_context"]))
            if _digest(saved.model_dump(mode="json")) != row["input_fingerprint"]:
                raise EnrichmentWorkflowError("enrichment_frozen_inputs_changed")
            loaded = load_event_enrichment_inputs(
                session, self.store, scope, UUID(row["event_id"]), row["rule_version"]
            )
            frozen = _freeze_inputs(session, loaded)
            if row["input_fingerprint"] != _digest(frozen.model_dump(mode="json")):
                raise EnrichmentWorkflowError("enrichment_frozen_inputs_changed")
            return saved
        except (PermissionError, EnrichmentInputError, EnrichmentWorkflowError, ValidationError):
            raise JobExecutionError("enrichment_frozen_inputs_changed", blocked=True) from None

    def initialize(
        self, session: Session, context: JobExecutionContext, payload: bytes
    ) -> JobExecutionResult:
        row, request, scope = self._workflow(session, context, payload)
        if request.step_key is not None or row["parent_job_id"] != context.job_id:
            raise JobExecutionError("enrichment_parent_binding_invalid", blocked=True)
        if row["initialized_at"] is not None:
            return JobExecutionResult(result_ref="pg:enrichment_workflow:" + row["workflow_id"])
        body = EventEnrichmentRequest.model_validate_json(json.dumps(row["request_payload"]))
        try:
            loaded = load_event_enrichment_inputs(
                session, self.store, scope, UUID(row["event_id"]), row["rule_version"]
            )
            if loaded.context.expected_event_version != body.expected_event_version:
                raise EnrichmentWorkflowError("enrichment_event_version_changed")
            _lock_input_parents(session, loaded)
            _require_current_inputs(session, scope, loaded)
            frozen = _freeze_inputs(session, loaded)
        except (
            EnrichmentInputError,
            EnrichmentPublicationError,
            EnrichmentWorkflowError,
            PermissionError,
        ):
            raise JobExecutionError("enrichment_frozen_inputs_changed", blocked=True) from None
        self._execution_scope(session, row, lock=True)
        at = self.clock()
        session.execute(
            update(enrichment_workflows)
            .where(enrichment_workflows.c.workflow_id == row["workflow_id"])
            .values(
                input_context=frozen.model_dump(mode="json"),
                input_fingerprint=_digest(frozen.model_dump(mode="json")),
                initialized_at=at,
            )
        )
        for step in physical_steps(body):
            self._enqueue_step(
                session,
                row,
                request,
                step.step_key,
                at,
                dimension=step.dimension,
                provider=step.provider,
                output_token_budget=step.output_token_budget,
            )
        self._enqueue_step(session, row, request, "publication", at)
        return JobExecutionResult(result_ref="pg:enrichment_workflow:" + row["workflow_id"])

    def _enqueue_step(
        self,
        session: Session,
        row: RowMapping,
        payload: EnrichmentJobPayload,
        key: str,
        at: datetime,
        *,
        dimension: str | None = None,
        provider: str | None = None,
        output_token_budget: int = 0,
    ) -> None:
        max_attempts = 3
        if key == "publication":
            max_attempts = 10
        elif dimension in MODEL_DIMENSIONS or dimension == "exposure":
            max_attempts = 1
        job_id = enqueue_job(
            session,
            row["tenant_id"],
            ENRICHMENT_PUBLICATION_JOB_TYPE if key == "publication" else ENRICHMENT_STEP_JOB_TYPE,
            json_payload(payload.model_copy(update={"step_key": key})),
            at,
            idempotency_key=f"{row['workflow_id']}:{key}",
            max_attempts=max_attempts,
        )
        session.execute(
            insert(enrichment_job_steps).values(
                job_id=job_id,
                workflow_id=row["workflow_id"],
                step_key=key,
                dimension=dimension,
                provider=provider,
                output_token_budget=output_token_budget,
                created_at=at,
            )
        )

    def _reserve_model_call(self, job_id: str, at: datetime) -> bool:
        """UPDATE avoids the executor's job FK lock; main step locks must follow reservation."""
        with Session(self.engine) as reservation, reservation.begin():
            reserved = reservation.execute(
                update(enrichment_job_steps)
                .where(
                    enrichment_job_steps.c.job_id == job_id,
                    enrichment_job_steps.c.model_call_reserved_at.is_(None),
                )
                .values(model_call_reserved_at=at)
                .returning(enrichment_job_steps.c.job_id)
            ).scalar_one_or_none()
            return reserved is not None

    def _record_model_receipt(
        self, job_id: str, attempts: tuple[AttemptMetadata, ...], at: datetime
    ) -> None:
        with Session(self.engine) as receipt, receipt.begin():
            receipt.execute(
                update(enrichment_job_steps)
                .where(
                    enrichment_job_steps.c.job_id == job_id,
                    enrichment_job_steps.c.model_call_reserved_at.is_not(None),
                    enrichment_job_steps.c.model_call_completed_at.is_(None),
                )
                .values(
                    model_call_completed_at=at,
                    model_trace=MODEL_TRACE_ADAPTER.dump_python(attempts, mode="json"),
                )
            )

    def execute_step(
        self, session: Session, context: JobExecutionContext, payload: bytes
    ) -> JobExecutionResult:
        row, request, scope = self._workflow(session, context, payload)
        step = (
            session.execute(
                select(enrichment_job_steps).where(
                    enrichment_job_steps.c.job_id == context.job_id,
                    enrichment_job_steps.c.workflow_id == row["workflow_id"],
                    enrichment_job_steps.c.step_key == request.step_key,
                )
            )
            .mappings()
            .first()
        )
        if step is None or step["dimension"] is None or row["initialized_at"] is None:
            raise JobExecutionError("enrichment_step_binding_invalid", blocked=True)
        frozen = self._current_inputs(session, row, scope)
        dimension = step["dimension"]
        if step["result_payload"] is not None:
            if _digest(step["result_payload"]) != step["result_sha256"]:
                raise JobExecutionError("enrichment_step_result_digest_invalid", blocked=True)
            attempt = DimensionAttempt.model_validate_json(json.dumps(step["result_payload"]))
        elif dimension in MODEL_DIMENSIONS:
            attempt = self._model_attempt(row, step, frozen, context.job_id)
        elif dimension == "exposure":
            attempt = self._exposure_attempt(row, step)
        else:
            attempt = next(
                attempt
                for attempt in enrich_structured_fields(frozen.context, frozen.loaded().documents)
                if attempt.dimension == dimension
            )
        self._execution_scope(session, row)
        self._current_inputs(session, row, scope)
        encoded = attempt.model_dump(mode="json")
        session.execute(
            update(enrichment_job_steps)
            .where(enrichment_job_steps.c.job_id == context.job_id)
            .values(
                result_payload=encoded,
                result_sha256=_digest(encoded),
                result_recorded_at=self.clock(),
            )
        )
        result = _attempt_outcome(attempt)
        return JobExecutionResult(
            result.outcome, "pg:enrichment_step:" + context.job_id, result.error_code
        )

    def _model_attempt(
        self,
        row: RowMapping,
        step: RowMapping,
        frozen: FrozenEnrichmentInputs,
        job_id: str,
    ) -> DimensionAttempt:
        policy = EnrichmentExecutionPolicy.model_validate_json(json.dumps(row["execution_policy"]))
        code: str | None = None
        client = None
        if not policy.generation_enabled:
            code = "model_budget_not_authorized"
        elif row["visibility"] == "tenant" and not policy.private_egress_granted:
            code = "model_egress_denied"
        elif self.generation_client_factory is None:
            code = "model_not_configured"
        else:
            client = self.generation_client_factory()
            if client is None:
                code = "model_not_configured"
            elif (
                not isinstance(client, GenerationClient)
                or client.provider != policy.generation_provider
                or client.approved_model != policy.approved_model
                or client.limits.max_calls != 1
                or client.limits.total_timeout_seconds > 20
            ):
                code = "model_client_policy_invalid"
        if code:
            return DimensionAttempt(
                dimension=step["dimension"], status=DimensionStatus.BLOCKED, error_code=code
            )
        if not self._reserve_model_call(job_id, self.clock()):
            return DimensionAttempt(
                dimension=step["dimension"],
                status=DimensionStatus.FAILED,
                error_code="incomplete_interrupted",
            )
        try:
            generated = extract_model_dimension(
                frozen.context,
                frozen.loaded().documents,
                client,
                dimension=step["dimension"],
                budget_authorized=True,
                content_is_private=row["visibility"] == "tenant",
                egress_granted=policy.private_egress_granted,
                total_output_token_budget=1024,
            )
        except FieldEvidenceError as error:
            self._record_model_receipt(job_id, (), self.clock())
            return DimensionAttempt(
                dimension=step["dimension"], status=DimensionStatus.FAILED, error_code=error.code
            )
        self._record_model_receipt(job_id, generated.model_attempts, self.clock())
        return generated.attempts[0]

    def _exposure_attempt(self, row: RowMapping, step: RowMapping) -> DimensionAttempt:
        request = EventEnrichmentRequest.model_validate_json(json.dumps(row["request_payload"]))
        policy = EnrichmentExecutionPolicy.model_validate_json(json.dumps(row["execution_policy"]))
        if request.product_query_id is None:
            return DimensionAttempt(
                dimension="exposure", status=DimensionStatus.PENDING, error_code="exposure_unknown"
            )
        if not policy.aggregate_enabled or self.exposure_client is None:
            return DimensionAttempt(
                dimension="exposure",
                status=DimensionStatus.BLOCKED,
                error_code="aggregate_not_configured",
            )
        attempt = self.exposure_client.collect_aggregate(
            step["provider"], request.product_query_id, request_timeout_seconds=20.0
        )
        if (
            attempt.dimension != "exposure"
            or attempt.candidates
            or attempt.status
            in {
                DimensionStatus.AVAILABLE,
                DimensionStatus.CONFLICT,
            }
        ):
            raise JobExecutionError("aggregate_publication_not_connected", blocked=True)
        return attempt

    def publish(
        self, session: Session, context: JobExecutionContext, payload: bytes
    ) -> JobExecutionResult:
        row, request, scope = self._workflow(session, context, payload)
        publication = (
            session.execute(
                select(enrichment_job_steps).where(
                    enrichment_job_steps.c.job_id == context.job_id,
                    enrichment_job_steps.c.workflow_id == row["workflow_id"],
                    enrichment_job_steps.c.step_key == "publication",
                )
            )
            .mappings()
            .first()
        )
        if publication is None or request.step_key != "publication":
            raise JobExecutionError("enrichment_publication_binding_invalid", blocked=True)
        children = tuple(
            session.execute(
                select(enrichment_job_steps, job_runs.c.status, job_runs.c.error_code)
                .join(job_runs, job_runs.c.job_id == enrichment_job_steps.c.job_id)
                .where(
                    enrichment_job_steps.c.workflow_id == row["workflow_id"],
                    enrichment_job_steps.c.dimension.is_not(None),
                )
                .order_by(enrichment_job_steps.c.step_key)
            ).mappings()
        )
        if not children or any(child["status"] not in TERMINAL_STATUSES for child in children):
            raise JobExecutionError("enrichment_children_pending", retry_after_seconds=20.0)
        scope = self._execution_scope(session, row, lock=True)
        frozen = self._current_inputs(session, row, scope)
        body = EventEnrichmentRequest.model_validate_json(json.dumps(row["request_payload"]))
        structured = {
            attempt.dimension: attempt
            for attempt in enrich_structured_fields(frozen.context, frozen.loaded().documents)
        }
        for child in children:
            if child["result_payload"] is None and child["dimension"] in structured:
                recovered = structured[child["dimension"]].model_dump(mode="json")
                session.execute(
                    update(enrichment_job_steps)
                    .where(enrichment_job_steps.c.job_id == child["job_id"])
                    .values(
                        result_payload=recovered,
                        result_sha256=_digest(recovered),
                        result_recorded_at=self.clock(),
                    )
                )
        children = tuple(
            session.execute(
                select(enrichment_job_steps, job_runs.c.status, job_runs.c.error_code)
                .join(job_runs, job_runs.c.job_id == enrichment_job_steps.c.job_id)
                .where(
                    enrichment_job_steps.c.workflow_id == row["workflow_id"],
                    enrichment_job_steps.c.dimension.is_not(None),
                )
                .order_by(enrichment_job_steps.c.step_key)
            ).mappings()
        )
        attempts: list[DimensionAttempt] = []
        for dimension in body.dimensions:
            results = tuple(
                self._child_attempt(child) for child in children if child["dimension"] == dimension
            )
            if len(results) != (2 if dimension == "exposure" else 1):
                raise JobExecutionError("enrichment_child_roster_changed", blocked=True)
            attempts.append(
                combine_exposure_attempts(results) if dimension == "exposure" else results[0]
            )
        try:
            published = publish_enrichment_attempts(
                session,
                scope,
                frozen.loaded(),
                tuple(attempts),
                request_id=request.workflow_id,
                recorded_at=self.clock(),
            )
        except (EnrichmentPublicationError, PermissionError):
            raise JobExecutionError("enrichment_frozen_inputs_changed", blocked=True) from None
        receipt = {"result_ids": [result.result_id for result in published]}
        session.execute(
            update(enrichment_job_steps)
            .where(enrichment_job_steps.c.job_id == context.job_id)
            .values(
                result_payload=receipt,
                result_sha256=_digest(receipt),
                result_recorded_at=self.clock(),
            )
        )
        if any(_attempt_outcome(attempt).outcome != "succeeded" for attempt in attempts) or any(
            child["status"] != "succeeded" for child in children
        ):
            return JobExecutionResult("partial", "pg:enrichment_workflow:" + row["workflow_id"])
        return JobExecutionResult("succeeded", "pg:enrichment_workflow:" + row["workflow_id"])

    def _child_attempt(self, child: RowMapping) -> DimensionAttempt:
        if child["result_payload"] is not None:
            if _digest(child["result_payload"]) != child["result_sha256"]:
                raise JobExecutionError("enrichment_step_result_digest_invalid", blocked=True)
            attempt = DimensionAttempt.model_validate_json(json.dumps(child["result_payload"]))
            if attempt.dimension != child["dimension"]:
                raise JobExecutionError("enrichment_step_result_dimension_invalid", blocked=True)
            return attempt
        interrupted = (
            child["model_call_reserved_at"] is not None and child["model_call_completed_at"] is None
        )
        return DimensionAttempt(
            dimension=child["dimension"],
            status=DimensionStatus.BLOCKED
            if child["status"] == "blocked"
            else DimensionStatus.FAILED,
            error_code="incomplete_interrupted"
            if interrupted
            else child["error_code"] or "enrichment_step_incomplete",
        )

    def read_workflow(
        self,
        session: Session,
        scope: AccessScope,
        workflow_id: UUID,
        *,
        actor_session_hash: str,
        at: datetime,
    ) -> EnrichmentWorkflowView:
        current = _authenticated_scope(session, actor_session_hash, at)
        if current != scope:
            raise CrossTenantAccessError("resource not found")
        row = (
            session.execute(
                select(enrichment_workflows, job_runs.c.status.label("parent_status"))
                .join(job_runs, job_runs.c.job_id == enrichment_workflows.c.parent_job_id)
                .where(enrichment_workflows.c.workflow_id == str(workflow_id))
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        current.enforce_visible(row["visibility"], row["tenant_id"])
        current.requires(READ_PUBLIC if row["visibility"] == "public" else READ_ASSET)
        if current.user_id != row["actor_user_id"]:
            current.requires(_write_permission(row["visibility"]))
        revisions = EventRepository(session, current).get_source_revisions(row["event_id"])
        _require_input_scopes(
            session,
            current,
            VisibilityScope(visibility=row["visibility"], tenant_id=row["tenant_id"]),
            revisions,
        )
        if row["input_context"] is not None:
            saved = FrozenEnrichmentInputs.model_validate_json(json.dumps(row["input_context"]))
            _require_input_scopes(
                session, current, saved.scope, tuple(map(str, saved.context.revision_ids))
            )
        rows = tuple(
            session.execute(
                select(enrichment_job_steps, job_runs.c.status, job_runs.c.error_code)
                .join(job_runs, job_runs.c.job_id == enrichment_job_steps.c.job_id)
                .where(enrichment_job_steps.c.workflow_id == str(workflow_id))
                .order_by(enrichment_job_steps.c.step_key)
            ).mappings()
        )
        steps = tuple(self._step_view(item) for item in rows)
        publication = next((item for item in rows if item["step_key"] == "publication"), None)
        body = EventEnrichmentRequest.model_validate_json(json.dumps(row["request_payload"]))
        dimensions: list[EnrichmentDimensionView] = []
        for dimension in body.dimensions:
            children = tuple(item for item in rows if item["dimension"] == dimension)
            attempts = tuple(
                self._child_attempt(item)
                for item in children
                if item["status"] in TERMINAL_STATUSES
            )
            result = (
                combine_exposure_attempts(attempts)
                if dimension == "exposure" and attempts
                else next(iter(attempts), None)
            )
            dimensions.append(
                EnrichmentDimensionView(
                    dimension=dimension,
                    status=logical_job_status(tuple(item["status"] for item in children)),
                    error_code=(
                        result.error_code
                        if result and result.error_code
                        else next(
                            (child["error_code"] for child in children if child["error_code"]), None
                        )
                    ),
                    job_ids=tuple(UUID(item["job_id"]) for item in children),
                    result_status=result.status if result else None,
                )
            )
        return EnrichmentWorkflowView(
            workflow_id=workflow_id,
            parent_job_id=UUID(row["parent_job_id"]),
            event_id=UUID(row["event_id"]),
            data_mode=EnrichmentExecutionPolicy.model_validate_json(
                json.dumps(row["execution_policy"])
            ).data_mode,
            parent_status=row["parent_status"],
            scheduling_complete=row["initialized_at"] is not None,
            workflow_complete=bool(
                publication
                and publication["status"] in TERMINAL_STATUSES
                and row["parent_status"] in TERMINAL_STATUSES
                and all(item["status"] in TERMINAL_STATUSES for item in rows)
            ),
            publication_status=publication["status"] if publication else None,
            logical_dimensions=tuple(dimensions),
            steps=steps,
            created_at=row["created_at"],
            initialized_at=row["initialized_at"],
        )

    def _step_view(self, row: RowMapping) -> EnrichmentStepView:
        call_state: ModelCallState = "not_reserved"
        if row["model_call_reserved_at"] is not None:
            call_state = (
                "completed"
                if row["model_call_completed_at"] is not None
                else (
                    "incomplete_interrupted" if row["status"] in TERMINAL_STATUSES else "reserved"
                )
            )
        return EnrichmentStepView(
            job_id=UUID(row["job_id"]),
            step_key=row["step_key"],
            dimension=row["dimension"],
            provider=row["provider"],
            status=row["status"],
            error_code=row["error_code"],
            output_token_budget=row["output_token_budget"],
            model_call_state=call_state,
            model_attempts=MODEL_TRACE_ADAPTER.validate_json(json.dumps(row["model_trace"])),
        )
