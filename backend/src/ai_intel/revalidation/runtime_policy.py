"""Trusted PG ownership and existing jobs/outbox drive bounded reassessment children."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from pydantic import SecretStr, ValidationError
from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from ai_intel.api.actor_references import (
    ActorJobOwner,
    ActorReference,
    actor_reference_from_payload,
    actor_reference_payload,
    lock_actor_job_scope,
    lock_actor_reference_scope,
)
from ai_intel.assets.inventory_models import assets
from ai_intel.domain.access import READ_ASSET, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import job_payloads, job_runs, scope_epochs
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.revalidation.candidates import (
    CandidateDiscoveryError,
    CandidateDiscoveryService,
    read_current_rule_scope_fingerprint,
)
from ai_intel.revalidation.execution_contracts import (
    ReassessmentRequest,
    RevalidationChangeRequest,
    RevalidationFanInManifest,
    RevalidationPlan,
)
from ai_intel.revalidation.fan_in import (
    check_fan_in,
    guard_completed_fan_in,
    read_completed_assessments,
    require_current_scope,
)
from ai_intel.revalidation.persistence_models import revalidation_job_bindings
from ai_intel.revalidation.service import LATEST_RULE_QUERY, RevalidationError, RevalidationService
from ai_intel.revalidation.verified_content import (
    FrozenVerifiedContent,
    VerificationBudgetExceeded,
    VerifiedContentInvalid,
    VerifiedFanInResult,
    VerifiedSourceProof,
)
from ai_intel.workers.executor import (
    DetachedJobHandler,
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
)
from ai_intel.workers.jobs import record_job_transition, require_job_lease

REASSESSMENT_JOB_TYPE = "revalidate_assessment"
REVALIDATION_CHANGE_JOB_TYPE = "revalidate_change"


class RevalidationJobOwner:
    """Only the immutable authenticated binding is an owner; ordinary payloads are not."""

    def lock_actor_job_owner(self, connection: Connection, job_id: str) -> ActorJobOwner | None:
        return self._read_actor_job_owner(connection, job_id, lock_job=True)

    def read_actor_job_owner(self, connection: Connection, job_id: str) -> ActorJobOwner | None:
        """Immutable bindings can prove dependencies without locking another executing job."""
        return self._read_actor_job_owner(connection, job_id, lock_job=False)

    def _read_actor_job_owner(
        self, connection: Connection, job_id: str, *, lock_job: bool
    ) -> ActorJobOwner | None:
        query = (
            select(
                revalidation_job_bindings,
                job_runs.c.job_type,
                job_runs.c.payload_sha256.label("job_digest"),
                job_runs.c.payload_ref,
            )
            .join(job_runs, job_runs.c.job_id == revalidation_job_bindings.c.job_id)
            .where(job_runs.c.job_id == job_id)
        )
        if lock_job:
            query = query.with_for_update(of=(job_runs, revalidation_job_bindings))
        row = connection.execute(query).mappings().first()
        if row is None or row["job_type"] not in {
            REASSESSMENT_JOB_TYPE,
            REVALIDATION_CHANGE_JOB_TYPE,
        }:
            return None
        if row["payload_sha256"] != row["job_digest"] or row["payload_ref"] != "pg:job:" + job_id:
            return None
        stored_payload = connection.execute(
            select(job_payloads.c.payload).where(job_payloads.c.job_id == job_id)
        ).scalar_one_or_none()
        if stored_payload is None:
            return None
        payload = bytes(stored_payload)
        if hashlib.sha256(payload).hexdigest() != row["payload_sha256"]:
            return None
        try:
            if row["job_type"] == REASSESSMENT_JOB_TYPE:
                ReassessmentRequest.model_validate_json(payload)
            else:
                RevalidationChangeRequest.model_validate_json(payload)
            reference = actor_reference_from_payload(row["actor_reference"])
            role = Role(row["authorized_role"])
        except (ValidationError, ValueError, PermissionDeniedError):
            return None
        if (
            reference.credential_kind != "session"
            or reference.tenant_id is None
            or reference.tenant_id != row["tenant_id"]
            or reference.user_id != row["actor_user_id"]
            or reference.role != role
        ):
            return None
        return ActorJobOwner(reference.user_id, reference.tenant_id, role, row["actor_reference"])


def _enqueue_owned_job(
    session: Session,
    actor: ActorReference,
    job_type: str,
    payload: bytes,
    created_at: datetime,
    *,
    max_attempts: int = 3,
) -> str:
    scope = lock_actor_reference_scope(session.connection(), actor, created_at)
    scope.requires(READ_ASSET)
    if actor.credential_kind != "session" or scope.tenant_id is None:
        raise PermissionDeniedError("tenant session required for revalidation jobs")
    digest = hashlib.sha256(payload).hexdigest()
    authority_digest = hashlib.sha256(
        repr((actor.session_hash, actor.role.value, actor.permissions_digest)).encode()
    ).hexdigest()
    key_digest = hashlib.sha256(f"{actor.user_id}:{authority_digest}:{digest}".encode()).hexdigest()
    job_id = enqueue_job(
        session,
        scope.tenant_id,
        job_type,
        payload,
        created_at,
        idempotency_key="revalidation:" + key_digest,
        max_attempts=max_attempts,
    )
    prior = (
        session.execute(
            select(revalidation_job_bindings).where(revalidation_job_bindings.c.job_id == job_id)
        )
        .mappings()
        .first()
    )
    if prior is None:
        session.execute(
            insert(revalidation_job_bindings).values(
                job_id=job_id,
                actor_user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                authorized_role=actor.role.value,
                actor_reference=actor_reference_payload(actor),
                payload_sha256=digest,
                created_at=created_at,
            )
        )
    else:
        previous_actor = actor_reference_from_payload(prior["actor_reference"])
        if (
            prior["actor_user_id"] != actor.user_id
            or prior["tenant_id"] != scope.tenant_id
            or prior["payload_sha256"] != digest
            or previous_actor.permissions != actor.permissions
            or previous_actor.role != actor.role
            or previous_actor.session_hash != actor.session_hash
        ):
            raise PermissionDeniedError("revalidation job ownership changed")
    return job_id


def enqueue_revalidation_change(
    session: Session,
    actor: ActorReference,
    request: RevalidationChangeRequest,
    created_at: datetime,
) -> str:
    """Server authentication constructs the actor; no public request supplies identity fields."""
    request = RevalidationChangeRequest.model_validate(request.model_dump(mode="python"))
    scope = lock_actor_reference_scope(session.connection(), actor, created_at)
    scope.requires(READ_ASSET)
    if actor.credential_kind != "session" or scope.tenant_id is None:
        raise PermissionDeniedError("tenant session required for revalidation jobs")
    change = (
        session.execute(
            select(change_events).where(
                change_events.c.change_id == request.change_id,
                change_events.c.scope_key.in_(("public", "tenant:" + scope.tenant_id)),
            )
        )
        .mappings()
        .first()
    )
    if change is None:
        raise PermissionDeniedError("resource not found")
    CandidateDiscoveryService._authorize_change(session, scope, change)
    current_epoch = session.scalar(
        select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == change["scope_key"])
    )
    if (
        current_epoch is None
        or not change["epoch"] <= request.target_epoch <= current_epoch
        or request.assessment_created_before > created_at
    ):
        raise RevalidationError("revalidation_change_not_authoritative")
    if request.fan_in is not None and (
        request.fan_in.effective_epoch != current_epoch
        or request.frozen_scope_epoch_map is None
        or request.frozen_scope_epoch_map.get(change["scope_key"]) != current_epoch
    ):
        raise RevalidationError("revalidation_change_not_authoritative")
    return _enqueue_owned_job(
        session,
        actor,
        REVALIDATION_CHANGE_JOB_TYPE,
        request.model_dump_json().encode(),
        created_at,
        max_attempts=request.fan_in.remaining_checks if request.fan_in is not None else 3,
    )


def enqueue_reassessment_plan(
    session: Session, actor: ActorReference, plan: RevalidationPlan, created_at: datetime
) -> tuple[str, ...]:
    """Authenticated immutable ownership, child input and outbox commit in the same transaction."""
    scope = lock_actor_reference_scope(session.connection(), actor, created_at)
    scope.requires(READ_ASSET)
    if actor.credential_kind != "session" or scope.tenant_id is None:
        raise PermissionDeniedError("tenant session required for revalidation jobs")
    if (
        plan.actor_user_id != scope.user_id
        or plan.tenant_id != scope.tenant_id
        or plan.permission_version != scope.permission_version
        or plan.permissions_digest != actor.permissions_digest
    ):
        raise PermissionDeniedError("revalidation plan authentication changed")
    change = (
        session.execute(
            select(change_events.c.scope_key, change_events.c.epoch).where(
                change_events.c.change_id == plan.change_id,
                change_events.c.scope_key.in_(("public", "tenant:" + scope.tenant_id)),
            )
        )
        .mappings()
        .first()
    )
    if change is None or not change["epoch"] <= plan.target_epoch:
        raise RevalidationError("revalidation_change_not_authoritative")
    snapshots: dict[str, str | None] = {}
    for asset_id in sorted({target.asset_id for target in plan.targets}):
        snapshots[asset_id] = session.scalar(
            select(assets.c.current_snapshot_id)
            .where(
                assets.c.asset_id == asset_id,
                assets.c.tenant_id == scope.tenant_id,
                assets.c.active.is_(True),
            )
            .with_for_update(read=True)
        )
    epochs = {
        row.scope_key: row.epoch
        for row in session.execute(
            select(scope_epochs.c.scope_key, scope_epochs.c.epoch)
            .where(scope_epochs.c.scope_key.in_(plan.scope_epoch_map))
            .order_by(scope_epochs.c.scope_key)
            .with_for_update(read=True)
        )
    }
    if {key: epochs.get(key) for key in plan.scope_epoch_map} != plan.scope_epoch_map:
        raise RevalidationError("revalidation_plan_inputs_changed")
    if epochs.get(change["scope_key"]) != plan.target_epoch:
        raise RevalidationError("revalidation_plan_inputs_changed")
    if (
        plan.rule_scope_fingerprint is None
        or read_current_rule_scope_fingerprint(session, scope) != plan.rule_scope_fingerprint
    ):
        raise RevalidationError("revalidation_plan_inputs_changed")
    children: list[str] = []
    for target in plan.targets:
        latest_rule = session.execute(
            text(LATEST_RULE_QUERY + "AND v.rule_id=:rule_id AND v.version=:version"),
            {"tenant": scope.tenant_id, "rule_id": target.rule_id, "version": target.rule_version},
        ).first()
        if snapshots[target.asset_id] != target.asset_snapshot_id or latest_rule is None:
            raise RevalidationError("revalidation_plan_inputs_changed")
        request = ReassessmentRequest(
            change_id=plan.change_id,
            target_epoch=plan.target_epoch,
            **target.model_dump(mode="python"),
        )
        payload = request.model_dump_json().encode()
        job_id = _enqueue_owned_job(session, actor, REASSESSMENT_JOB_TYPE, payload, created_at)
        children.append(job_id)
    return tuple(children)


def make_reassessment_handler(
    engine: Engine, content_store: ContentStorage, cursor_signing_key: SecretStr
) -> DetachedJobHandler:
    """Release the short claim transaction before the shared service opens its own locks."""

    def reassess(context: JobExecutionContext, payload: bytes) -> JobExecutionResult:
        request = ReassessmentRequest.model_validate_json(payload)
        try:
            with Session(engine) as session, session.begin():
                actor = _lock_bound_actor(session, context, payload)
            outcome = RevalidationService(
                engine, actor, content_store, cursor_signing_key
            ).reassess(request)
        except PermissionError:
            raise JobExecutionError("revalidation_authority_revoked", blocked=True) from None
        except RevalidationError as error:
            raise JobExecutionError(str(error)) from None
        return JobExecutionResult(
            outcome=outcome.execution_status,
            result_ref="pg:assessment:" + outcome.assessment.assessment_id,
            error_code=outcome.incomplete_reasons[0] if outcome.incomplete_reasons else None,
        )

    return DetachedJobHandler(reassess)


def _lock_bound_actor(
    session: Session, context: JobExecutionContext, payload: bytes
) -> ActorReference:
    binding = (
        session.execute(
            select(revalidation_job_bindings).where(
                revalidation_job_bindings.c.job_id == context.job_id
            )
        )
        .mappings()
        .first()
    )
    if binding is None or binding["tenant_id"] != context.tenant_id:
        raise JobExecutionError("revalidation_job_binding_unavailable", blocked=True)
    actor = actor_reference_from_payload(binding["actor_reference"])
    scope = lock_actor_job_scope(
        session.connection(),
        actor,
        datetime.now(UTC),
        job_id=context.job_id,
        owner_port=RevalidationJobOwner(),
    )
    scope.requires(READ_ASSET)
    if hashlib.sha256(payload).hexdigest() != binding["payload_sha256"]:
        raise JobExecutionError("revalidation_payload_changed", blocked=True)
    require_job_lease(
        session,
        context.job_id,
        context.worker_id,
        datetime.now(UTC),
        expected_attempt=context.attempt_count,
    )
    return actor


def _pause_continuation(session: Session, job_id: str, reason: str, at: datetime) -> None:
    row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
    if row["status"] == "queued":
        session.execute(
            update(job_runs)
            .where(job_runs.c.job_id == job_id)
            .values(status="blocked", error_code=reason, updated_at=at, finished_at=at)
        )
        record_job_transition(session, dict(row), "blocked", reason, at)


def _enqueue_completion_job(
    session: Session,
    actor: ActorReference,
    request: RevalidationChangeRequest,
    parent_job_id: str,
    plan: RevalidationPlan,
    child_job_ids: tuple[str, ...],
    next_page_job_id: str | None,
    incomplete_reasons: tuple[str, ...],
    created_at: datetime,
) -> str:
    completion_request = request.model_copy(
        update={
            "continuation": None,
            "rule_after_id": None,
            "frozen_scope_epoch_map": plan.scope_epoch_map,
            "frozen_rule_scope_fingerprint": plan.rule_scope_fingerprint,
            "fan_in": RevalidationFanInManifest(
                parent_job_id=parent_job_id,
                effective_epoch=plan.target_epoch,
                child_job_ids=child_job_ids,
                next_page_job_id=next_page_job_id,
                plan_incomplete_reasons=incomplete_reasons,
            ),
        }
    )
    return enqueue_revalidation_change(session, actor, completion_request, created_at)


def make_revalidation_change_handler(
    engine: Engine, content_store: ContentStorage, cursor_signing_key: SecretStr
) -> DetachedJobHandler:
    """One frozen candidate page plus at most 64 rules; continuation stays in owned PG jobs."""

    def plan_change(context: JobExecutionContext, payload: bytes) -> JobExecutionResult:
        request = RevalidationChangeRequest.model_validate_json(payload)
        try:
            with Session(engine) as session, session.begin():
                actor = _lock_bound_actor(session, context, payload)
                if request.fan_in is not None:
                    result, completed_children = check_fan_in(session, actor, request, context)
            if request.fan_in is not None:
                if result.outcome == "succeeded":
                    content_by_hash = read_completed_assessments(
                        engine, actor, content_store, request, completed_children
                    )
                    if actor.tenant_id is None:
                        raise PermissionDeniedError("tenant session required for revalidation jobs")
                    proof = VerifiedSourceProof(
                        job_id=context.job_id,
                        worker_id=context.worker_id,
                        attempt_count=context.attempt_count,
                        tenant_id=actor.tenant_id,
                        actor=actor,
                        request_sha256=hashlib.sha256(payload).hexdigest(),
                        content_by_hash=content_by_hash,
                    )
                    return VerifiedFanInResult(
                        result.outcome, result.result_ref, result.error_code, proof=proof
                    )
                return result
            service = RevalidationService(engine, actor, content_store, cursor_signing_key)
            try:
                plan = service.plan_change(
                    request.change_id,
                    request.target_epoch,
                    assessment_created_before=request.assessment_created_before,
                    continuation=request.continuation,
                    rule_after_id=request.rule_after_id,
                    frozen_scope_epoch_map=request.frozen_scope_epoch_map,
                    frozen_rule_scope_fingerprint=request.frozen_rule_scope_fingerprint,
                )
            except (CandidateDiscoveryError, RevalidationError) as error:
                if str(error) not in {
                    "candidate_cursor_context_changed",
                    "revalidation_continuation_context_changed",
                    "revalidation_continuation_context_missing",
                } or (request.continuation is None and request.rule_after_id is None):
                    raise
                request = request.model_copy(
                    update={
                        "continuation": None,
                        "rule_after_id": None,
                        "frozen_scope_epoch_map": None,
                        "frozen_rule_scope_fingerprint": None,
                    }
                )
                plan = service.plan_change(
                    request.change_id,
                    request.target_epoch,
                    assessment_created_before=request.assessment_created_before,
                )
            now = datetime.now(UTC)
            with Session(engine) as session, session.begin():
                _lock_bound_actor(session, context, payload)
                if len(plan.targets) > request.remaining_children:
                    budget_completion_job = _enqueue_completion_job(
                        session,
                        actor,
                        request,
                        context.job_id,
                        plan,
                        (),
                        None,
                        ("revalidation_child_budget_exhausted",),
                        now,
                    )
                    return JobExecutionResult(
                        outcome="partial",
                        result_ref="pg:job:" + budget_completion_job,
                        error_code="revalidation_child_budget_exhausted",
                    )
                children = enqueue_reassessment_plan(session, actor, plan, now)
                has_continuation = (
                    plan.next_rule_after_id is not None or plan.continuation is not None
                )
                next_job = None
                stopped = None
                if has_continuation:
                    remaining_children = request.remaining_children - len(plan.targets)
                    remaining_pages = request.remaining_pages - 1
                    if remaining_pages == 0:
                        stopped = "revalidation_page_budget_exhausted"
                    elif remaining_children == 0:
                        stopped = "revalidation_child_budget_exhausted"
                    next_request = request.model_copy(
                        update={
                            "remaining_pages": max(1, remaining_pages),
                            "remaining_children": max(1, remaining_children),
                            "continuation": request.continuation
                            if plan.next_rule_after_id is not None
                            else plan.continuation,
                            "rule_after_id": plan.next_rule_after_id,
                            "frozen_scope_epoch_map": plan.scope_epoch_map,
                            "frozen_rule_scope_fingerprint": plan.rule_scope_fingerprint,
                        }
                    )
                    next_job = enqueue_revalidation_change(session, actor, next_request, now)
                    if stopped is not None:
                        _pause_continuation(session, next_job, stopped, now)
                outcome: Literal["succeeded", "partial"] = "succeeded"
                error_code = stopped
                if has_continuation or plan.targets or plan.incomplete_reasons:
                    outcome = "partial"
                if error_code is None and plan.targets:
                    error_code = "revalidation_child_jobs_pending"
                if error_code is None and plan.incomplete_reasons:
                    error_code = plan.incomplete_reasons[0]
                completion_job = None
                if has_continuation or children or plan.incomplete_reasons:
                    incomplete_reasons = tuple(
                        reason
                        for reason in plan.incomplete_reasons
                        if reason
                        not in {"candidate_pages_remaining", "visible_rule_roster_budget_exceeded"}
                    )
                    if stopped is not None:
                        incomplete_reasons = (*incomplete_reasons, stopped)
                    completion_job = _enqueue_completion_job(
                        session,
                        actor,
                        request,
                        context.job_id,
                        plan,
                        children,
                        next_job,
                        incomplete_reasons,
                        now,
                    )
                return JobExecutionResult(
                    outcome=outcome,
                    result_ref="pg:job:" + completion_job
                    if completion_job
                    else "pg:change:" + request.change_id,
                    error_code=error_code,
                )
        except PermissionError:
            raise JobExecutionError("revalidation_authority_revoked", blocked=True) from None
        except VerificationBudgetExceeded:
            return JobExecutionResult(
                "partial",
                "pg:change:" + request.change_id,
                "revalidation_verification_budget_exhausted",
            )
        except VerifiedContentInvalid as error:
            raise JobExecutionError(str(error), blocked=True) from None
        except RevalidationError as error:
            raise JobExecutionError(str(error)) from None
        except CandidateDiscoveryError as error:
            raise JobExecutionError(str(error), blocked=True) from None

    def guard_completion(
        session: Session, context: JobExecutionContext, payload: bytes, result: JobExecutionResult
    ) -> None:
        request = RevalidationChangeRequest.model_validate_json(payload)
        if request.fan_in is None:
            return
        try:
            actor = _lock_bound_actor(session, context, payload)
            require_current_scope(session, actor, request)
            if result.outcome == "succeeded":
                if not isinstance(result, VerifiedFanInResult):
                    raise VerifiedContentInvalid("revalidation_verified_proof_unavailable")
                proof = result.proof
                if (
                    proof.job_id != context.job_id
                    or proof.worker_id != context.worker_id
                    or proof.attempt_count != context.attempt_count
                    or proof.tenant_id != context.tenant_id
                    or proof.actor != actor
                    or proof.request_sha256 != hashlib.sha256(payload).hexdigest()
                ):
                    raise VerifiedContentInvalid("revalidation_verified_proof_identity_changed")
                guard_completed_fan_in(
                    session, engine, actor, FrozenVerifiedContent(proof), request, context
                )
        except PermissionError:
            raise JobExecutionError("revalidation_authority_revoked", blocked=True) from None
        except RevalidationError as error:
            raise JobExecutionError(str(error), blocked=True) from None
        except VerifiedContentInvalid as error:
            raise JobExecutionError(str(error), blocked=True) from None
        except VerificationBudgetExceeded:
            raise JobExecutionError(
                "revalidation_verification_budget_exhausted", blocked=True
            ) from None

    return DetachedJobHandler(plan_change, completion_guard=guard_completion)


def make_revalidation_job_handlers(
    engine: Engine, content_store: ContentStorage, cursor_signing_key: SecretStr
) -> dict[str, DetachedJobHandler]:
    """The root worker registers these fixed server handlers; payloads cannot select code."""
    return {
        REVALIDATION_CHANGE_JOB_TYPE: make_revalidation_change_handler(
            engine, content_store, cursor_signing_key
        ),
        REASSESSMENT_JOB_TYPE: make_reassessment_handler(engine, content_store, cursor_signing_key),
    }
