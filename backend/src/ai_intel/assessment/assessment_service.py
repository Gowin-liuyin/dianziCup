"""Fixed-snapshot assessment with an authenticated PG preparation receipt and final recheck."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.assessment.assessment_persistence import assessment_results, assessment_scope_watches
from ai_intel.assessment.conditions import (
    ComponentMatches,
    ConditionEvaluation,
    InventoryProvesAbsence,
    VersionInRange,
    iter_condition_nodes,
)
from ai_intel.assessment.persistence_contracts import (
    ASSESSMENT_POLICY_VERSION,
    AssessmentReceipt,
    AssessmentScopeWatch,
    PreparedAssessment,
    RuleInputSnapshot,
)
from ai_intel.assessment.rule_persistence import (
    RulePersistenceError,
    load_rule_inputs,
    lock_rule_inputs,
    read_rule,
    receipt_values,
    require_snapshot_source_access,
    rule_validation_receipts,
    stored_rule,
)
from ai_intel.assessment.rules import evaluate_rule
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.domain.access import (
    READ_ASSET,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.domain.enums import AssessmentStatus, FreshnessStatus, RuleStatus
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.persistence import publication_payload_digest


def build_scope_watch(
    inputs: RuleInputSnapshot, snapshot: AssetSnapshotResponse
) -> AssessmentScopeWatch:
    keys = {component.ecosystem + ":" + component.package_name for component in snapshot.components}
    for node in iter_condition_nodes(inputs.rule.condition_ast):
        if isinstance(node, VersionInRange):
            keys.add(node.assertion.ecosystem + ":" + node.assertion.package_key)
        elif isinstance(node, ComponentMatches | InventoryProvesAbsence):
            keys.add(node.ecosystem + ":" + node.package_key)
    published = inputs.rule.status == RuleStatus.PUBLISHED
    return AssessmentScopeWatch(
        tenant_id=snapshot.tenant_id,
        event_ids=(inputs.rule.event_id,),
        package_keys=tuple(sorted(keys)),
        rule_id=inputs.rule.rule_id,
        rule_version=inputs.rule.version,
        rule_kind=inputs.rule.rule_kind,
        scope_epoch_map=inputs.scope_epoch_map,
        selected_rule_ids=(inputs.rule.rule_id,) if published else (),
        no_published_rule=not published,
    )


def _asset_fingerprint(row: RowMapping) -> str:
    return publication_payload_digest(
        {
            str(key): value.isoformat() if isinstance(value, datetime) else value
            for key, value in row.items()
        }
    )


def _bind_source_evidence(
    tree: ConditionEvaluation,
    inputs: RuleInputSnapshot,
) -> ConditionEvaluation:
    refs = tuple(
        item.evidence.evidence_id
        for item in inputs.supports
        if item.binding.node_id == tree.node_id
    )
    children = tuple(_bind_source_evidence(child, inputs) for child in tree.child_results)
    return tree.model_copy(
        update={
            "evidence_ids": tuple(dict.fromkeys((*tree.evidence_ids, *refs))),
            "child_results": children,
        }
    )


class AssessmentService:
    """Prepare verifies blobs outside final locks; commit trusts only its persisted PG receipt."""

    def __init__(self, engine: Engine, session_token: str, content_store: ContentStorage) -> None:
        self.engine = engine
        self._session_token = session_token
        self.content_store = content_store

    @staticmethod
    def _asset(
        session: Session, scope: AccessScope, asset_id: str, *, lock: bool = False
    ) -> RowMapping:
        scope.requires(READ_ASSET)
        if scope.tenant_id is None:
            raise PermissionDeniedError("tenant asset scope required")
        query = select(assets).where(
            assets.c.asset_id == asset_id, assets.c.tenant_id == scope.tenant_id
        )
        if lock:
            query = query.with_for_update(read=True)
        row = session.execute(query).mappings().first()
        if row is None:
            raise CrossTenantAccessError("resource not found")
        return row

    @staticmethod
    def _snapshot(
        session: Session, scope: AccessScope, asset_id: str, snapshot_id: str
    ) -> AssetSnapshotResponse:
        row = (
            session.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.asset_id == asset_id,
                    asset_snapshots.c.tenant_id == scope.tenant_id,
                    asset_snapshots.c.snapshot_id == snapshot_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        snapshot = AssetSnapshotResponse.model_validate(row["canonical_payload"])
        if (
            hashlib.sha256(bytes(row["raw_input"])).hexdigest() != row["raw_input_sha256"]
            or snapshot.snapshot_sha256 != row["manifest_sha256"]
            or snapshot.snapshot_id != snapshot_id
            or snapshot.asset_id != asset_id
            or snapshot.tenant_id != scope.tenant_id
        ):
            raise RulePersistenceError("asset_snapshot_integrity_invalid")
        return snapshot

    def prepare(
        self, asset_id: str, snapshot_id: str, rule_id: str, version: int
    ) -> PreparedAssessment:
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(
                session.connection(), self._session_token, datetime.now(UTC)
            )
            asset = self._asset(session, scope, asset_id)
            snapshot = self._snapshot(session, scope, asset_id, snapshot_id)
            row = read_rule(session, scope, rule_id, version)
            inputs = load_rule_inputs(session, scope, row, self.content_store)
            watch = build_scope_watch(inputs, snapshot)
            asset_fingerprint = _asset_fingerprint(asset)
            digest = publication_payload_digest(
                [
                    snapshot.model_dump(mode="json"),
                    asset_fingerprint,
                    inputs.input_digest,
                    watch.model_dump(mode="json"),
                    ASSESSMENT_POLICY_VERSION,
                ]
            )
            preparation_id = str(uuid4())
            prepared = PreparedAssessment(
                preparation_receipt_id=preparation_id,
                actor_user_id=scope.user_id,
                actor_role=scope.role.value,
                permission_version=scope.permission_version,
                asset_snapshot=snapshot,
                asset_active=asset["active"],
                asset_current_snapshot_id=asset["current_snapshot_id"],
                asset_fingerprint=asset_fingerprint,
                inputs=inputs,
                scope_watch=watch,
                input_digest=digest,
            )
            session.execute(
                insert(rule_validation_receipts).values(
                    **receipt_values(inputs, scope.user_id, preparation_id),
                    prepared_assessment=prepared.model_dump(mode="json"),
                )
            )
            return prepared

    def commit(self, prepared: PreparedAssessment) -> AssessmentReceipt:
        prepared = PreparedAssessment.model_validate(prepared.model_dump(mode="python"))
        now = datetime.now(UTC)
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(session.connection(), self._session_token, now)
            if (
                scope.user_id != prepared.actor_user_id
                or scope.role.value != prepared.actor_role
                or scope.permission_version != prepared.permission_version
            ):
                raise PermissionDeniedError("assessment authentication context changed")
            snapshot = prepared.asset_snapshot
            asset = self._asset(session, scope, snapshot.asset_id, lock=True)
            staged = session.execute(
                select(rule_validation_receipts.c.prepared_assessment).where(
                    rule_validation_receipts.c.receipt_id == prepared.preparation_receipt_id,
                    rule_validation_receipts.c.actor_user_id == scope.user_id,
                )
            ).scalar()
            if staged is None or PreparedAssessment.model_validate(staged) != prepared:
                raise RulePersistenceError("assessment_preparation_receipt_mismatch")
            if self._snapshot(session, scope, snapshot.asset_id, snapshot.snapshot_id) != snapshot:
                raise RulePersistenceError("assessment_snapshot_mismatch")
            row = read_rule(
                session, scope, prepared.inputs.rule.rule_id, prepared.inputs.rule.version
            )
            lock_rule_inputs(session, stored_rule(row), scope)
            row = read_rule(
                session, scope, prepared.inputs.rule.rule_id, prepared.inputs.rule.version
            )
            current = load_rule_inputs(session, scope, row, None)
            require_snapshot_source_access(session, scope, current.rule.scope, prepared.inputs)
            prior = (
                session.execute(
                    select(assessment_results).where(
                        assessment_results.c.tenant_id == scope.tenant_id,
                        assessment_results.c.asset_snapshot_id == snapshot.snapshot_id,
                        assessment_results.c.rule_id == prepared.inputs.rule.rule_id,
                        assessment_results.c.rule_version == prepared.inputs.rule.version,
                        assessment_results.c.input_digest == prepared.input_digest,
                        assessment_results.c.policy_version == ASSESSMENT_POLICY_VERSION,
                    )
                )
                .mappings()
                .first()
            )
            if prior is not None:
                return self._read_result(session, scope, prior).model_copy(update={"reused": True})
            stale = (
                current.input_digest != prepared.inputs.input_digest
                or _asset_fingerprint(asset) != prepared.asset_fingerprint
                or asset["current_snapshot_id"] != snapshot.snapshot_id
                or not asset["active"]
            )
            usable = (
                prepared.inputs.rule.status == RuleStatus.PUBLISHED
                and prepared.inputs.validation.eligible
            )
            result = (
                evaluate_rule(prepared.inputs.rule, snapshot, access_scope=scope)
                if usable
                else None
            )
            if result is not None:
                result = result.model_copy(
                    update={
                        "evaluation_tree": _bind_source_evidence(
                            result.evaluation_tree, prepared.inputs
                        ),
                    }
                )
            receipt = AssessmentReceipt(
                assessment_id=str(uuid4()),
                tenant_id=snapshot.tenant_id,
                asset_id=snapshot.asset_id,
                asset_snapshot_id=snapshot.snapshot_id,
                event_id=prepared.inputs.rule.event_id,
                rule_id=prepared.inputs.rule.rule_id,
                rule_version=prepared.inputs.rule.version,
                knowledge_epoch=prepared.inputs.scope_epoch_map["public"],
                scope_epoch_map=prepared.inputs.scope_epoch_map,
                rule_result=result,
                status=AssessmentStatus.INSUFFICIENT_EVIDENCE if result is None else result.status,
                freshness=FreshnessStatus.STALE if stale else FreshnessStatus.CURRENT,
                missing_requirements=("unsupported_rule",)
                if result is None
                else result.evaluation_tree.missing_requirements,
                conflicts=prepared.inputs.validation.conflicts
                if result is None
                else result.evaluation_tree.observed_conflict_ids,
                limitations=("pending_semantic_review",) if result is None else result.limitations,
                exposure_result="observed_path_only"
                if prepared.inputs.rule.rule_kind == "observed_path"
                else "not_evaluated",
                prepared=prepared,
                input_digest=prepared.input_digest,
                created_at=now,
            )
            session.execute(
                insert(assessment_results).values(
                    assessment_id=receipt.assessment_id,
                    tenant_id=receipt.tenant_id,
                    asset_id=receipt.asset_id,
                    asset_snapshot_id=receipt.asset_snapshot_id,
                    event_id=receipt.event_id,
                    rule_id=receipt.rule_id,
                    rule_version=receipt.rule_version,
                    knowledge_epoch=receipt.knowledge_epoch,
                    scope_epoch_map=receipt.scope_epoch_map,
                    policy_version=ASSESSMENT_POLICY_VERSION,
                    input_digest=receipt.input_digest,
                    status=receipt.status.value,
                    freshness=receipt.freshness.value,
                    result_payload=receipt.model_dump(mode="json"),
                    created_at=now,
                )
            )
            watch_payload = prepared.scope_watch.model_dump(mode="json")
            session.execute(
                insert(assessment_scope_watches).values(
                    assessment_id=receipt.assessment_id, **watch_payload
                )
            )
            return receipt

    def read(self, assessment_id: str) -> AssessmentReceipt:
        with Session(self.engine) as session, session.begin():
            scope = lock_authenticated_scope(
                session.connection(), self._session_token, datetime.now(UTC)
            )
            scope.requires(READ_ASSET)
            row = (
                session.execute(
                    select(assessment_results).where(
                        assessment_results.c.assessment_id == assessment_id,
                        assessment_results.c.tenant_id == scope.tenant_id,
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            return self._read_result(session, scope, row)

    def _read_result(
        self, session: Session, scope: AccessScope, row: RowMapping
    ) -> AssessmentReceipt:
        receipt = AssessmentReceipt.model_validate(row["result_payload"])
        asset = self._asset(session, scope, receipt.asset_id, lock=True)
        rule = read_rule(session, scope, receipt.rule_id, receipt.rule_version)
        lock_rule_inputs(session, stored_rule(rule), scope)
        current = load_rule_inputs(
            session, scope, read_rule(session, scope, receipt.rule_id, receipt.rule_version), None
        )
        require_snapshot_source_access(session, scope, current.rule.scope, receipt.prepared.inputs)
        stale = (
            receipt.freshness == FreshnessStatus.STALE
            or current.input_digest != receipt.prepared.inputs.input_digest
            or asset["current_snapshot_id"] != receipt.asset_snapshot_id
            or not asset["active"]
            or _asset_fingerprint(asset) != receipt.prepared.asset_fingerprint
        )
        return receipt.model_copy(
            update={"freshness": FreshnessStatus.STALE if stale else FreshnessStatus.CURRENT}
        )
