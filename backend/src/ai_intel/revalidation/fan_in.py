"""Owned PG cohorts converge without revising the terminal planning job or assessments."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session

from ai_intel.api.actor_references import (
    ActorReference,
    actor_reference_from_payload,
    lock_actor_reference_scope,
)
from ai_intel.api.knowledge_read_service import sources
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assets.inventory_models import assets
from ai_intel.domain.access import READ_ASSET, PermissionDeniedError
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    job_runs,
    scope_epochs,
)
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.revalidation.candidates import (
    CURRENT_RULE_SCOPE_QUERY,
    CandidateDiscoveryService,
    read_current_rule_scope_fingerprint,
)
from ai_intel.revalidation.execution_contracts import ReassessmentRequest, RevalidationChangeRequest
from ai_intel.revalidation.persistence_models import revalidation_job_bindings
from ai_intel.revalidation.service import REVALIDATION_TIMEOUT_SECONDS, _require_remaining
from ai_intel.revalidation.verified_content import VerifiedContentInvalid, VerifiedContentRecorder
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError, JobExecutionResult
from ai_intel.workers.jobs import read_job_payload

PENDING_STATUSES = frozenset({"queued", "running", "retry_wait"})


def summarize_dependency_statuses(
    statuses: tuple[str | None, ...],
    attempt_count: int,
    remaining_checks: int,
    incomplete_reasons: tuple[str, ...],
) -> JobExecutionResult:
    """Work completion is independent of the four-state risk conclusion in each receipt."""
    known = PENDING_STATUSES | {
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "blocked",
        "waiting_approval",
        None,
    }
    if any(status not in known for status in statuses):
        return JobExecutionResult("blocked", error_code="revalidation_dependency_status_invalid")
    if "blocked" in statuses:
        return JobExecutionResult("blocked", error_code="revalidation_dependency_blocked")
    if None in statuses:
        return JobExecutionResult("partial", error_code="revalidation_dependency_unavailable")
    if set(statuses) & {"failed", "cancelled"}:
        return JobExecutionResult("partial", error_code="revalidation_dependency_failed")
    if set(statuses) & {"partial", "waiting_approval"}:
        return JobExecutionResult("partial", error_code="revalidation_dependency_incomplete")
    if set(statuses) & PENDING_STATUSES:
        if attempt_count >= remaining_checks:
            return JobExecutionResult(
                "partial", error_code="revalidation_completion_budget_exhausted"
            )
        raise JobExecutionError("revalidation_completion_pending", retry_after_seconds=5.0)
    if incomplete_reasons:
        return JobExecutionResult("partial", error_code=incomplete_reasons[0])
    return JobExecutionResult()


@dataclass(frozen=True)
class OwnedDependency:
    job_id: str
    status: str
    result_ref: str | None
    request: ReassessmentRequest | RevalidationChangeRequest


def read_owned_dependency(
    session: Session, actor: ActorReference, job_id: str
) -> OwnedDependency | None:
    """A reference is useful only with its immutable payload digest and exact bound actor."""
    from ai_intel.revalidation.runtime_policy import RevalidationJobOwner

    row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().first()
    if row is None:
        return None
    if row["tenant_id"] != actor.tenant_id:
        raise PermissionDeniedError("resource not found")
    scope = lock_actor_reference_scope(session.connection(), actor, datetime.now(UTC))
    scope.requires(READ_ASSET)
    owner = RevalidationJobOwner().read_actor_job_owner(session.connection(), job_id)
    if (
        owner is None
        or owner.user_id != actor.user_id
        or owner.tenant_id != actor.tenant_id
        or owner.authorized_role != actor.role
        or actor_reference_from_payload(owner.actor_reference) != actor
    ):
        raise PermissionDeniedError("resource not found")
    row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().first()
    if row is None or row["tenant_id"] != actor.tenant_id:
        raise PermissionDeniedError("resource not found")
    payload = read_job_payload(session, job_id, actor.tenant_id)
    binding_digest = session.scalar(
        select(revalidation_job_bindings.c.payload_sha256).where(
            revalidation_job_bindings.c.job_id == job_id
        )
    )
    if (
        binding_digest is None
        or row["payload_sha256"] != binding_digest
        or hashlib.sha256(payload).hexdigest() != binding_digest
        or row["payload_ref"] != "pg:job:" + job_id
    ):
        raise JobExecutionError("revalidation_dependency_payload_changed", blocked=True)
    if row["job_type"] == "revalidate_assessment":
        request: ReassessmentRequest | RevalidationChangeRequest = (
            ReassessmentRequest.model_validate_json(payload)
        )
    elif row["job_type"] == "revalidate_change":
        request = RevalidationChangeRequest.model_validate_json(payload)
    else:
        raise JobExecutionError("revalidation_dependency_type_invalid", blocked=True)
    return OwnedDependency(job_id, row["status"], row["result_ref"], request)


def require_same_change(
    dependency: OwnedDependency,
    request: RevalidationChangeRequest,
    *,
    allow_requested_epoch: bool = False,
) -> None:
    related = dependency.request
    effective_epoch = request.fan_in.effective_epoch if request.fan_in else request.target_epoch
    if isinstance(related, RevalidationChangeRequest):
        if related.fan_in is not None:
            epoch_matches = (
                related.target_epoch == request.target_epoch
                and related.fan_in.effective_epoch == effective_epoch
            )
        else:
            epoch_matches = (
                related.target_epoch <= effective_epoch
                if allow_requested_epoch
                else related.target_epoch == request.target_epoch
            )
    else:
        epoch_matches = related.target_epoch == effective_epoch
    if related.change_id != request.change_id or not epoch_matches:
        raise JobExecutionError("revalidation_dependency_input_mismatch", blocked=True)
    if isinstance(related, RevalidationChangeRequest) and (
        related.assessment_created_before != request.assessment_created_before
    ):
        raise JobExecutionError("revalidation_dependency_input_mismatch", blocked=True)


def internal_job_id(reference: str | None) -> str:
    if reference is None or not reference.startswith("pg:job:"):
        raise JobExecutionError("revalidation_completion_reference_invalid", blocked=True)
    identity = reference.removeprefix("pg:job:")
    try:
        if str(UUID(identity)) != identity:
            raise ValueError
    except ValueError:
        raise JobExecutionError("revalidation_completion_reference_invalid", blocked=True) from None
    return identity


def read_continuation_status(
    session: Session,
    actor: ActorReference,
    request: RevalidationChangeRequest,
    completion_job_id: str,
) -> str | None:
    """Only one exact page and its fixed completion reference may be inspected."""
    manifest = request.fan_in
    if manifest is None or manifest.next_page_job_id is None:
        return "succeeded"
    page = read_owned_dependency(session, actor, manifest.next_page_job_id)
    if page is None:
        return None
    require_same_change(page, request)
    if not isinstance(page.request, RevalidationChangeRequest) or page.request.fan_in is not None:
        raise JobExecutionError("revalidation_continuation_input_invalid", blocked=True)
    if (
        page.request.frozen_scope_epoch_map != request.frozen_scope_epoch_map
        or page.request.frozen_rule_scope_fingerprint != request.frozen_rule_scope_fingerprint
    ):
        raise JobExecutionError("revalidation_continuation_inputs_changed", blocked=True)
    if page.status != "partial":
        if page.status == "succeeded" and page.result_ref != "pg:change:" + request.change_id:
            raise JobExecutionError("revalidation_completion_reference_invalid", blocked=True)
        return page.status
    check_id = internal_job_id(page.result_ref)
    if check_id in {
        completion_job_id,
        manifest.parent_job_id,
        *manifest.child_job_ids,
        page.job_id,
    }:
        raise JobExecutionError("revalidation_completion_reference_cycle", blocked=True)
    check = read_owned_dependency(session, actor, check_id)
    if check is None:
        return None
    require_same_change(check, request)
    if (
        not isinstance(check.request, RevalidationChangeRequest)
        or check.request.fan_in is None
        or check.request.fan_in.parent_job_id != page.job_id
        or check.request.frozen_scope_epoch_map != request.frozen_scope_epoch_map
        or check.request.frozen_rule_scope_fingerprint != request.frozen_rule_scope_fingerprint
    ):
        raise JobExecutionError("revalidation_continuation_input_invalid", blocked=True)
    if check.status == "succeeded" and check.result_ref != "pg:change:" + request.change_id:
        raise JobExecutionError("revalidation_completion_reference_invalid", blocked=True)
    return check.status


def read_fan_in_dependencies(
    session: Session,
    actor: ActorReference,
    request: RevalidationChangeRequest,
    context: JobExecutionContext,
) -> tuple[tuple[OwnedDependency, ...], tuple[str | None, ...]]:
    manifest = request.fan_in
    if manifest is None:
        raise JobExecutionError("revalidation_completion_manifest_missing", blocked=True)
    if context.job_id in {
        manifest.parent_job_id,
        *manifest.child_job_ids,
        manifest.next_page_job_id,
    }:
        raise JobExecutionError("revalidation_completion_reference_cycle", blocked=True)
    parent = read_owned_dependency(session, actor, manifest.parent_job_id)
    if parent is None:
        return (), (None,)
    require_same_change(parent, request, allow_requested_epoch=True)
    if (
        not isinstance(parent.request, RevalidationChangeRequest)
        or parent.request.fan_in is not None
    ):
        raise JobExecutionError("revalidation_completion_parent_invalid", blocked=True)
    if parent.status in PENDING_STATUSES:
        return (), (parent.status,)
    if parent.status != "partial" or parent.result_ref != "pg:job:" + context.job_id:
        raise JobExecutionError("revalidation_completion_parent_invalid", blocked=True)
    children: list[OwnedDependency] = []
    statuses: list[str | None] = []
    for job_id in manifest.child_job_ids:
        child = read_owned_dependency(session, actor, job_id)
        if child is None:
            statuses.append(None)
            continue
        require_same_change(child, request)
        if not isinstance(child.request, ReassessmentRequest):
            raise JobExecutionError("revalidation_dependency_type_invalid", blocked=True)
        children.append(child)
        statuses.append(child.status)
    statuses.append(read_continuation_status(session, actor, request, context.job_id))
    return tuple(children), tuple(statuses)


def require_current_scope(
    session: Session, actor: ActorReference, request: RevalidationChangeRequest
) -> None:
    from ai_intel.api.actor_references import lock_actor_reference_scope

    scope = lock_actor_reference_scope(session.connection(), actor, datetime.now(UTC))
    expected = request.frozen_scope_epoch_map
    if expected is None or set(expected) != {"public", "tenant:" + str(scope.tenant_id)}:
        raise JobExecutionError("revalidation_completion_inputs_changed", blocked=True)
    current = {
        key: session.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == key))
        for key in expected
    }
    change = (
        session.execute(
            select(change_events).where(
                change_events.c.change_id == request.change_id,
                change_events.c.scope_key.in_(expected),
            )
        )
        .mappings()
        .first()
    )
    if change is None:
        raise PermissionDeniedError("resource not found")
    CandidateDiscoveryService._authorize_change(session, scope, change)
    if (
        current != expected
        or request.fan_in is None
        or current[change["scope_key"]] != request.fan_in.effective_epoch
        or read_current_rule_scope_fingerprint(session, scope)
        != request.frozen_rule_scope_fingerprint
    ):
        raise JobExecutionError("revalidation_completion_inputs_changed", blocked=True)


def assessment_id_for_child(child: OwnedDependency) -> str:
    reference = child.result_ref
    if reference is None or not reference.startswith("pg:assessment:"):
        raise JobExecutionError("revalidation_assessment_reference_invalid", blocked=True)
    identity = reference.removeprefix("pg:assessment:")
    try:
        if str(UUID(identity)) != identity:
            raise ValueError
    except ValueError:
        raise JobExecutionError("revalidation_assessment_reference_invalid", blocked=True) from None
    return identity


def require_current_child_receipt(
    child: OwnedDependency, receipt: AssessmentReceipt, request: RevalidationChangeRequest
) -> None:
    if not isinstance(child.request, ReassessmentRequest) or (
        receipt.asset_id != child.request.asset_id
        or receipt.rule_id != child.request.rule_id
        or request.frozen_scope_epoch_map is None
        or "tenant:" + receipt.tenant_id not in request.frozen_scope_epoch_map
    ):
        raise JobExecutionError("revalidation_assessment_identity_changed", blocked=True)
    if receipt.freshness != FreshnessStatus.CURRENT or (
        receipt.scope_epoch_map != request.frozen_scope_epoch_map
    ):
        raise JobExecutionError("revalidation_assessment_stale", blocked=True)


def check_fan_in(
    session: Session,
    actor: ActorReference,
    request: RevalidationChangeRequest,
    context: JobExecutionContext,
) -> tuple[JobExecutionResult, tuple[OwnedDependency, ...]]:
    manifest = request.fan_in
    if manifest is None:
        raise JobExecutionError("revalidation_completion_manifest_missing", blocked=True)
    require_current_scope(session, actor, request)
    children, statuses = read_fan_in_dependencies(session, actor, request, context)
    result = summarize_dependency_statuses(
        statuses, context.attempt_count, manifest.remaining_checks, manifest.plan_incomplete_reasons
    )
    return JobExecutionResult(
        result.outcome, "pg:change:" + request.change_id, result.error_code
    ), children


def read_completed_assessments(
    engine: Engine,
    actor: ActorReference,
    store: ContentStorage,
    request: RevalidationChangeRequest,
    children: tuple[OwnedDependency, ...],
) -> Mapping[str, bytes]:
    """Public assessment reads recheck provenance and permissions after short job locks release."""
    deadline = time.monotonic() + REVALIDATION_TIMEOUT_SECONDS
    source_hashes: set[str] = set()
    with Session(engine) as session, session.begin():
        scope = lock_actor_reference_scope(session.connection(), actor, datetime.now(UTC))
        scope.requires(READ_ASSET)
        for child in children:
            _require_remaining(deadline)
            payload = session.scalar(
                select(assessment_results.c.result_payload).where(
                    assessment_results.c.assessment_id == assessment_id_for_child(child),
                    assessment_results.c.tenant_id == actor.tenant_id,
                )
            )
            if payload is None:
                raise VerifiedContentInvalid("revalidation_assessment_unavailable")
            receipt = AssessmentReceipt.model_validate(payload)
            source_hashes.update(
                source.content_sha256 for source in receipt.prepared.inputs.sources
            )
        sizes: dict[str, int] = {}
        for row in session.execute(
            select(content_objects.c.content_hash, content_objects.c.size_bytes).where(
                content_objects.c.content_hash.in_(sorted(source_hashes))
            )
        ):
            content_hash, size_bytes = row
            if (
                not isinstance(content_hash, str)
                or not isinstance(size_bytes, int)
                or type(size_bytes) is not int
            ):
                raise VerifiedContentInvalid("revalidation_verified_source_size_unavailable")
            sizes[content_hash] = size_bytes
    recorder = VerifiedContentRecorder(store, sizes)
    assessor = AssessmentService(engine, actor, recorder)
    for child in children:
        _require_remaining(deadline)
        receipt = assessor.read(assessment_id_for_child(child))
        require_current_child_receipt(child, receipt, request)
    _require_remaining(deadline)
    return recorder.freeze()


def lock_completion_inputs(
    session: Session,
    actor: ActorReference,
    rows: tuple[RowMapping, ...],
) -> None:
    """Lock the combined source closure before publication, avoiding per-rule lock inversion."""
    snapshot_receipts = tuple(
        AssessmentReceipt.model_validate(row["result_payload"]) for row in rows
    )
    asset_ids = sorted({receipt.asset_id for receipt in snapshot_receipts})
    session.execute(
        select(assets.c.asset_id)
        .where(assets.c.asset_id.in_(asset_ids), assets.c.tenant_id == actor.tenant_id)
        .order_by(assets.c.asset_id)
        .with_for_update()
    ).all()
    source_ids: set[str] = set()
    revision_ids: set[str] = set()
    roster: object = session.execute(
        text(CURRENT_RULE_SCOPE_QUERY), {"tenant": actor.tenant_id}
    ).scalar_one()
    if not isinstance(roster, list):
        raise JobExecutionError("revalidation_completion_scope_invalid", blocked=True)
    for rule in roster:
        if not isinstance(rule, dict) or not isinstance(rule.get("sources"), list):
            raise JobExecutionError("revalidation_completion_scope_invalid", blocked=True)
        for source in rule["sources"]:
            if (
                not isinstance(source, list)
                or len(source) != 11
                or not isinstance(source[0], str)
                or not isinstance(source[8], str)
            ):
                raise JobExecutionError("revalidation_completion_scope_invalid", blocked=True)
            revision_ids.add(source[0])
            source_ids.add(source[8])
    for receipt in snapshot_receipts:
        for source_input in receipt.prepared.inputs.sources:
            source_ids.add(source_input.source_id)
            revision_ids.add(source_input.revision_id)
    for source_id in sorted(source_ids):
        session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended("source:" + source_id, 0)))
        )
    session.execute(
        select(sources.c.source_id)
        .where(sources.c.source_id.in_(sorted(source_ids)))
        .order_by(sources.c.source_id)
        .with_for_update(read=True)
    ).all()
    session.execute(
        select(document_revisions.c.revision_id)
        .join(documents, documents.c.document_id == document_revisions.c.document_id)
        .where(document_revisions.c.revision_id.in_(sorted(revision_ids)))
        .order_by(documents.c.document_id, document_revisions.c.revision_id)
        .with_for_update(read=True, of=(documents, document_revisions))
    ).all()
    for scope_key in sorted({"public", "tenant:" + str(actor.tenant_id)}):
        session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended("knowledge-publication:" + scope_key, 0)
                )
            )
        )
    session.execute(
        select(scope_epochs.c.scope_key)
        .where(scope_epochs.c.scope_key.in_(("public", "tenant:" + str(actor.tenant_id))))
        .order_by(scope_epochs.c.scope_key)
        .with_for_update(read=True)
    ).all()


def guard_completed_fan_in(
    session: Session,
    engine: Engine,
    actor: ActorReference,
    store: ContentStorage,
    request: RevalidationChangeRequest,
    context: JobExecutionContext,
) -> None:
    """The worker invokes this in the same leased transaction as its terminal job write."""
    from ai_intel.api.actor_references import lock_actor_reference_scope

    deadline = time.monotonic() + REVALIDATION_TIMEOUT_SECONDS
    result, children = check_fan_in(session, actor, request, context)
    if result.outcome != "succeeded":
        raise JobExecutionError("revalidation_completion_inputs_changed", blocked=True)
    rows: list[RowMapping] = []
    for child in children:
        row = (
            session.execute(
                select(assessment_results).where(
                    assessment_results.c.assessment_id == assessment_id_for_child(child),
                    assessment_results.c.tenant_id == actor.tenant_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise JobExecutionError("revalidation_assessment_unavailable", blocked=True)
        rows.append(row)
    _require_remaining(deadline)
    lock_completion_inputs(session, actor, tuple(rows))
    require_current_scope(session, actor, request)
    scope = lock_actor_reference_scope(session.connection(), actor, datetime.now(UTC))
    assessor = AssessmentService(engine, actor, store)
    for child, row in zip(children, rows, strict=True):
        _require_remaining(deadline)
        receipt = assessor._read_result(session, scope, row)
        require_current_child_receipt(child, receipt, request)
    _require_remaining(deadline)
    require_current_scope(session, actor, request)
