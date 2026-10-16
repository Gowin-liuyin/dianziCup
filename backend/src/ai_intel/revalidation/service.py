"""Recompute authorized current assessments without overwriting their historical receipts."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_intel.api.actor_references import ActorReference
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.rule_persistence import stored_rule
from ai_intel.assets.inventory_models import assets
from ai_intel.domain.access import READ_ASSET, CrossTenantAccessError, PermissionDeniedError
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.models import scope_epochs
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.revalidation.candidate_contracts import AssessmentChangeCandidate
from ai_intel.revalidation.candidates import (
    LATEST_RULE_QUERY,
    CandidateDiscoveryService,
    read_current_rule_scope_fingerprint,
)
from ai_intel.revalidation.execution_contracts import (
    ReassessmentOutcome,
    ReassessmentRequest,
    ReassessmentTarget,
    RevalidationPlan,
)

MAX_VISIBLE_RULES = 64
MAX_REASSESSMENT_TARGETS = 100
REVALIDATION_TIMEOUT_SECONDS = 20.0


class RevalidationError(ValueError):
    """Fixed codes preserve incomplete planning and stale commits as observable failures."""


def _require_remaining(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise RevalidationError("revalidation_deadline_exceeded")


def unique_current_assets(
    candidates: tuple[AssessmentChangeCandidate, ...],
) -> tuple[tuple[str, str], ...]:
    """Several historical assessments select one current snapshot per affected asset."""
    snapshots: dict[str, str] = {}
    for candidate in candidates:
        if candidate.asset_id in snapshots and (
            snapshots[candidate.asset_id] != candidate.asset_snapshot_id
        ):
            raise RevalidationError("revalidation_candidate_snapshot_changed")
        snapshots[candidate.asset_id] = candidate.asset_snapshot_id
    return tuple(sorted(snapshots.items()))


class RevalidationService:
    """PG authenticated discovery followed by existing preparation/CAS/append-only commits.

    A plan freezes all pages before effects. Each child resolves the latest inputs again;
    a changed input may append a stale receipt, but cannot replace an earlier receipt.
    """

    def __init__(
        self,
        engine: Engine,
        actor: ActorReference,
        content_store: ContentStorage,
        cursor_signing_key: SecretStr,
    ) -> None:
        if not isinstance(actor, ActorReference):
            raise TypeError("revalidation requires an internal actor reference")
        if actor.credential_kind != "session" or actor.tenant_id is None:
            raise PermissionDeniedError("tenant session required for revalidation jobs")
        self.engine = engine
        self.actor = actor
        self.content_store = content_store
        self.discovery = CandidateDiscoveryService(engine, actor, cursor_signing_key)

    def plan_change(
        self,
        change_id: str,
        target_epoch: int,
        *,
        assessment_created_before: datetime | None = None,
        continuation: str | None = None,
        rule_after_id: str | None = None,
        frozen_scope_epoch_map: dict[str, int | None] | None = None,
        frozen_rule_scope_fingerprint: str | None = None,
    ) -> RevalidationPlan:
        """Discover before writing; fixed roster and target caps leave explicit partial plans."""
        deadline = time.monotonic() + REVALIDATION_TIMEOUT_SECONDS
        cutoff = (
            datetime.now(UTC) if assessment_created_before is None else assessment_created_before
        )
        reasons: list[str] = []
        _require_remaining(deadline)
        page = self.discovery.discover(
            change_id,
            target_epoch,
            limit=1,
            continuation=continuation,
            assessment_created_before=cutoff,
        )
        if rule_after_id is not None and (
            frozen_scope_epoch_map is None or frozen_rule_scope_fingerprint is None
        ):
            raise RevalidationError("revalidation_continuation_context_missing")
        if frozen_scope_epoch_map is not None and (
            frozen_scope_epoch_map != page.scope_epoch_map
            or frozen_rule_scope_fingerprint != page.rule_scope_fingerprint
        ):
            raise RevalidationError("revalidation_continuation_context_changed")
        if page.continuation is not None:
            reasons.append("candidate_pages_remaining")
        asset_refs = unique_current_assets(page.candidates)
        _require_remaining(deadline)
        rules: tuple[RowMapping, ...] = ()
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(session.connection(), self.actor, datetime.now(UTC))
            scope.requires(READ_ASSET)
            current_epochs = {
                key: session.scalar(
                    select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == key)
                )
                for key in page.scope_epoch_map
            }
            if (
                current_epochs != page.scope_epoch_map
                or read_current_rule_scope_fingerprint(session, scope)
                != page.rule_scope_fingerprint
            ):
                raise RevalidationError("revalidation_plan_inputs_changed")
            if asset_refs:
                rules = tuple(
                    session.execute(
                        text(
                            LATEST_RULE_QUERY
                            + ("AND v.rule_id>:rule_after_id " if rule_after_id is not None else "")
                            + "ORDER BY v.rule_id LIMIT :rule_limit"
                        ),
                        {
                            "tenant": scope.tenant_id,
                            "rule_limit": MAX_VISIBLE_RULES + 1,
                            "rule_after_id": rule_after_id,
                        },
                    ).mappings()
                )
        if len(rules) > MAX_VISIBLE_RULES:
            reasons.append("visible_rule_roster_budget_exceeded")
        if asset_refs and not rules:
            reasons.append("no_visible_rules_requires_scope_watch")
        targets: list[ReassessmentTarget] = []
        for asset_id, snapshot_id in asset_refs:
            for row in rules[:MAX_VISIBLE_RULES]:
                if len(targets) == MAX_REASSESSMENT_TARGETS:
                    if "reassessment_target_budget_exceeded" not in reasons:
                        reasons.append("reassessment_target_budget_exceeded")
                    break
                rule = stored_rule(row)
                targets.append(
                    ReassessmentTarget(
                        asset_id=asset_id,
                        asset_snapshot_id=snapshot_id,
                        rule_id=rule.rule_id,
                        rule_version=rule.version,
                    )
                )
        _require_remaining(deadline)
        return RevalidationPlan(
            change_id=change_id,
            actor_user_id=self.actor.user_id,
            tenant_id=str(self.actor.tenant_id),
            permission_version=self.actor.permission_version,
            permissions_digest=self.actor.permissions_digest,
            requested_epoch=target_epoch,
            target_epoch=page.target_epoch,
            scope_epoch_map=page.scope_epoch_map,
            rule_scope_fingerprint=page.rule_scope_fingerprint,
            assessment_created_before=cutoff,
            continuation=page.continuation,
            next_rule_after_id=rules[MAX_VISIBLE_RULES - 1]["rule_id"]
            if len(rules) > MAX_VISIBLE_RULES
            else None,
            targets=tuple(targets),
            candidate_count=len(page.candidates),
            planning_status="partial" if reasons else "complete",
            incomplete_reasons=tuple(reasons),
        )

    def reassess(self, request: ReassessmentRequest) -> ReassessmentOutcome:
        """Resolve current asset/rule rather than allowing an old job to revive old inputs."""
        request = ReassessmentRequest.model_validate(request.model_dump(mode="python"))
        deadline = time.monotonic() + REVALIDATION_TIMEOUT_SECONDS
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(session.connection(), self.actor, datetime.now(UTC))
            scope.requires(READ_ASSET)
            change = (
                session.execute(
                    select(change_events).where(
                        change_events.c.change_id == request.change_id,
                        change_events.c.scope_key.in_(("public", "tenant:" + str(scope.tenant_id))),
                    )
                )
                .mappings()
                .first()
            )
            if change is None:
                raise CrossTenantAccessError("resource not found")
            self.discovery._authorize_change(session, scope, change)
            current_epoch = session.scalar(
                select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == change["scope_key"])
            )
            if (
                current_epoch is None
                or not change["epoch"] <= request.target_epoch <= current_epoch
            ):
                raise RevalidationError("revalidation_target_epoch_invalid")
            asset = (
                session.execute(
                    select(assets).where(
                        assets.c.asset_id == request.asset_id,
                        assets.c.tenant_id == scope.tenant_id,
                        assets.c.active.is_(True),
                    )
                )
                .mappings()
                .first()
            )
            rule_row = (
                session.execute(
                    text(LATEST_RULE_QUERY + "AND v.rule_id=:rule_id"),
                    {"tenant": scope.tenant_id, "rule_id": request.rule_id},
                )
                .mappings()
                .first()
            )
            if asset is None or rule_row is None:
                raise CrossTenantAccessError("resource not found")
            snapshot_id = str(asset["current_snapshot_id"])
            version = stored_rule(rule_row).version
        _require_remaining(deadline)
        assessor = AssessmentService(self.engine, self.actor, self.content_store)
        prepared = assessor.prepare(request.asset_id, snapshot_id, request.rule_id, version)
        _require_remaining(deadline)
        try:
            receipt = assessor.commit(prepared)
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint != "uq_assessment_execution":
                raise
            _require_remaining(deadline)
            receipt = assessor.commit(prepared)
        _require_remaining(deadline)
        receipt = assessor.read(receipt.assessment_id)
        _require_remaining(deadline)
        reasons = (
            ("assessment_inputs_changed",) if receipt.freshness != FreshnessStatus.CURRENT else ()
        )
        return ReassessmentOutcome(
            assessment=receipt,
            execution_status="partial" if reasons else "succeeded",
            incomplete_reasons=reasons,
        )
