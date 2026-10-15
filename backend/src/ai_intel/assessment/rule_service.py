"""Authenticated internal review/publication operations; no model supplies policy or approval."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.assessment.conditions import AllOf, AnyOf, condition_digest, iter_condition_nodes
from ai_intel.assessment.persistence_contracts import RuleInputSnapshot, RuleSupportBinding
from ai_intel.assessment.rule_persistence import (
    RulePersistenceError,
    condition_rule_versions,
    load_rule_inputs,
    lock_rule_inputs,
    read_rule,
    receipt_values,
    require_rule_access,
    rule_leaf_reviews,
    rule_support_bindings,
    rule_validation_receipts,
    stored_rule,
)
from ai_intel.assessment.rules import ConditionRule
from ai_intel.domain.access import CrossTenantAccessError, PermissionDeniedError
from ai_intel.domain.enums import RuleStatus
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.persistence import publication_payload_digest, save_change_publication
from ai_intel.knowledge.persistence_models import events


class RuleService:
    """Each operation authenticates and owns a short PG transaction; no external calls."""

    def __init__(self, engine: Engine, session_token: str, content_store: ContentStorage) -> None:
        self.engine = engine
        self._session_token = session_token
        self.content_store = content_store

    def create_candidate(
        self,
        rule: ConditionRule,
        bindings: tuple[RuleSupportBinding, ...],
    ) -> ConditionRule:
        rule = ConditionRule.model_validate(rule.model_dump(mode="python"))
        bindings = tuple(RuleSupportBinding.model_validate(item.model_dump()) for item in bindings)
        if rule.status != RuleStatus.CANDIDATE or len(bindings) > 64:
            raise RulePersistenceError("bounded_candidate_rule_required")
        if len({(item.node_id, item.claim_id, item.evidence_id) for item in bindings}) != len(
            bindings
        ):
            raise RulePersistenceError("duplicate_rule_support")
        nodes = {
            node.node_id: node
            for node in iter_condition_nodes(rule.condition_ast)
            if not isinstance(node, AllOf | AnyOf)
        }
        if (
            any(item.node_id not in nodes for item in bindings)
            or set(rule.supporting_claim_ids) != {item.claim_id for item in bindings}
            or set(rule.source_span_ids) != {item.evidence_id for item in bindings}
        ):
            raise RulePersistenceError("rule_reference_binding_mismatch")
        now = datetime.now(UTC)
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(session.connection(), self._session_token, now)
            parent = (
                session.execute(select(events).where(events.c.event_id == rule.event_id))
                .mappings()
                .first()
            )
            if parent is None:
                raise CrossTenantAccessError("resource not found")
            parent_scope = VisibilityScope(
                visibility=parent["visibility"], tenant_id=parent["tenant_id"]
            )
            require_rule_access(scope, parent_scope, write=True)
            if rule.scope != parent_scope:
                raise RulePersistenceError("rule_scope_must_match_authenticated_event")
            lock_rule_inputs(session, rule, scope, lock_rule=False)
            family = (
                session.execute(
                    select(condition_rule_versions)
                    .where(
                        condition_rule_versions.c.rule_id == rule.rule_id,
                    )
                    .order_by(condition_rule_versions.c.version)
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if family is not None:
                family_rule = stored_rule(family)
                require_rule_access(scope, family_rule.scope, write=False)
                if (
                    family_rule.scope != rule.scope
                    or family_rule.event_id != rule.event_id
                    or family_rule.rule_kind != rule.rule_kind
                ):
                    raise RulePersistenceError("rule_family_identity_changed")
            prior = (
                session.execute(
                    select(condition_rule_versions).where(
                        condition_rule_versions.c.rule_id == rule.rule_id,
                        condition_rule_versions.c.version == rule.version,
                    )
                )
                .mappings()
                .first()
            )
            if prior is not None:
                require_rule_access(scope, stored_rule(prior).scope, write=False)
                old_bindings = tuple(
                    session.execute(
                        select(rule_support_bindings).where(
                            rule_support_bindings.c.rule_id == rule.rule_id,
                            rule_support_bindings.c.rule_version == rule.version,
                        )
                    ).mappings()
                )
                if prior["rule_payload"] != rule.model_dump(mode="json") or {
                    (item["node_id"], item["claim_id"], item["evidence_id"])
                    for item in old_bindings
                } != {(item.node_id, item.claim_id, item.evidence_id) for item in bindings}:
                    raise IdempotencyConflictError(
                        "rule version reused with different immutable content"
                    )
                return stored_rule(prior)
            session.execute(
                insert(condition_rule_versions).values(
                    rule_id=rule.rule_id,
                    version=rule.version,
                    event_id=rule.event_id,
                    visibility=rule.scope.visibility,
                    tenant_id=rule.scope.tenant_id,
                    rule_kind=rule.rule_kind,
                    condition_sha256=condition_digest(rule.condition_ast),
                    rule_payload=rule.model_dump(mode="json"),
                    status="candidate",
                    author_user_id=scope.user_id,
                    created_at=now,
                )
            )
            for item in bindings:
                session.execute(
                    insert(rule_support_bindings).values(
                        rule_id=rule.rule_id,
                        rule_version=rule.version,
                        **item.model_dump(),
                        condition_sha256=condition_digest(nodes[item.node_id]),
                    )
                )
            load_rule_inputs(
                session,
                scope,
                read_rule(session, scope, rule.rule_id, rule.version),
                self.content_store,
            )
            return rule

    def validate(self, rule_id: str, version: int) -> RuleInputSnapshot:
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(
                session.connection(), self._session_token, datetime.now(UTC)
            )
            row = read_rule(session, scope, rule_id, version)
            require_rule_access(scope, stored_rule(row).scope, write=True)
            lock_rule_inputs(session, stored_rule(row), scope)
            row = read_rule(session, scope, rule_id, version)
            inputs = load_rule_inputs(session, scope, row, self.content_store)
            session.execute(
                insert(rule_validation_receipts).values(
                    **receipt_values(inputs, scope.user_id, str(uuid4()))
                )
            )
            if inputs.validation.eligible and row["status"] == "candidate":
                session.execute(
                    update(condition_rule_versions)
                    .where(
                        condition_rule_versions.c.rule_id == rule_id,
                        condition_rule_versions.c.version == version,
                    )
                    .values(status="validated")
                )
            return inputs

    def record_leaf_review(
        self,
        rule_id: str,
        version: int,
        binding: RuleSupportBinding,
        *,
        decision: Literal["supports", "refutes"],
        reason: str,
        range_completeness_confirmed: bool = False,
    ) -> str:
        """Explicit review action is separate from candidates; absence leaves typed pending."""
        if (
            decision not in {"supports", "refutes"}
            or not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > 2000
            or any(ord(char) < 32 for char in reason)
            or type(range_completeness_confirmed) is not bool
        ):
            raise RulePersistenceError("explicit_semantic_review_required")
        binding = RuleSupportBinding.model_validate(binding.model_dump())
        now = datetime.now(UTC)
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(session.connection(), self._session_token, now)
            row = read_rule(session, scope, rule_id, version)
            require_rule_access(scope, stored_rule(row).scope, write=True)
            if scope.user_id == row["author_user_id"]:
                raise PermissionDeniedError("independent rule reviewer required")
            if row["status"] == "retired":
                raise RulePersistenceError("retired_rule_requires_new_version")
            lock_rule_inputs(session, stored_rule(row), scope)
            inputs = load_rule_inputs(
                session, scope, read_rule(session, scope, rule_id, version), self.content_store
            )
            support = next((item for item in inputs.supports if item.binding == binding), None)
            if support is None:
                raise RulePersistenceError("review_binding_missing")
            values = dict(
                rule_id=rule_id,
                rule_version=version,
                **binding.model_dump(),
                input_digest=support.input_digest,
                decision=decision,
                range_complete=range_completeness_confirmed,
                reason=reason,
                actor_user_id=scope.user_id,
            )
            prior = session.execute(
                select(rule_leaf_reviews.c.review_id).where(
                    *(rule_leaf_reviews.c[key] == value for key, value in values.items())
                )
            ).scalar()
            if prior is not None:
                return str(prior)
            review_id = str(uuid4())
            session.execute(
                insert(rule_leaf_reviews).values(
                    **values, review_id=review_id, actor_role=scope.role.value, created_at=now
                )
            )
            return review_id

    def publish(self, rule_id: str, version: int) -> ConditionRule:
        return self._transition(rule_id, version, retire=False)

    def retire(self, rule_id: str, version: int) -> ConditionRule:
        return self._transition(rule_id, version, retire=True)

    def _transition(self, rule_id: str, version: int, *, retire: bool) -> ConditionRule:
        now = datetime.now(UTC)
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(session.connection(), self._session_token, now)
            row = read_rule(session, scope, rule_id, version)
            require_rule_access(scope, stored_rule(row).scope, write=True)
            if scope.user_id == row["author_user_id"]:
                raise PermissionDeniedError("independent rule approver required")
            lock_rule_inputs(session, stored_rule(row), scope)
            row = read_rule(session, scope, rule_id, version)
            inputs = load_rule_inputs(session, scope, row, self.content_store)
            if (retire and row["status"] == "retired") or (
                not retire and row["status"] == "published"
            ):
                if not retire and not inputs.validation.eligible:
                    raise RulePersistenceError("rule_pending_or_invalid_support")
                return stored_rule(row)
            required_status = "published" if retire else "validated"
            if row["status"] != required_status:
                raise RulePersistenceError("rule_lifecycle_transition_rejected")
            if not retire:
                another_published = session.scalar(
                    select(condition_rule_versions.c.version).where(
                        condition_rule_versions.c.rule_id == rule_id,
                        condition_rule_versions.c.status == "published",
                        condition_rule_versions.c.version != version,
                    )
                )
                if another_published is not None:
                    raise RulePersistenceError("rule_requires_retirement_of_published_version")
            if not retire and not inputs.validation.eligible:
                raise RulePersistenceError("rule_pending_or_invalid_support")
            session.execute(
                insert(rule_validation_receipts).values(
                    **receipt_values(inputs, scope.user_id, str(uuid4()))
                )
            )
            session.execute(
                update(condition_rule_versions)
                .where(
                    condition_rule_versions.c.rule_id == rule_id,
                    condition_rule_versions.c.version == version,
                )
                .values(
                    **{"status": "retired", "retired_at": now}
                    if retire
                    else {"status": "published", "published_at": now, "published_by": scope.user_id}
                )
            )
            payload = dict(
                rule_id=rule_id,
                rule_version=version,
                input_digest=inputs.input_digest,
                policy_version=inputs.validation.policy_version,
                actor_user_id=scope.user_id,
            )
            save_change_publication(
                session,
                inputs.rule.scope,
                f"rule:{rule_id}:{version}:" + ("retired" if retire else "published"),
                payload,
                publication_payload_digest(payload),
                (),
                (rule_id,),
                now,
                "condition_rule_retired" if retire else "condition_rule_published",
            )
            return stored_rule(read_rule(session, scope, rule_id, version))
