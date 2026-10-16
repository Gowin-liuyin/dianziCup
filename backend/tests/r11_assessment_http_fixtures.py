"""Explicit unit-only immutable receipt; never used by an application provider."""

from datetime import UTC, datetime
from uuid import uuid4

from tests.unit.test_r11_pg_assessment_scope import candidate_inputs

from ai_intel.assessment.assessment_service import build_scope_watch
from ai_intel.assessment.persistence_contracts import AssessmentReceipt, PreparedAssessment
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse


def synthetic_receipt() -> AssessmentReceipt:
    snapshot = AssetSnapshotResponse(
        schema_version="r11-asset-candidate-1",
        snapshot_id=str(uuid4()),
        asset_id=str(uuid4()),
        tenant_id="fixture-tenant",
        snapshot_number=1,
        observed_at=datetime(2026, 10, 16, tzinfo=UTC),
        recorded_at=datetime(2026, 10, 16, tzinfo=UTC),
        source_kind="fixture",
        inventory_completeness="unknown",
        declared_scope=(),
        components=(),
        configuration=(),
        tool_permissions=None,
        input_channels=None,
        network_exposure=None,
        snapshot_sha256="b" * 64,
    )
    inputs = candidate_inputs()
    prepared = PreparedAssessment(
        preparation_receipt_id="private-preparation-marker",
        actor_user_id="private-actor-marker",
        actor_role="analyst",
        permission_version=1,
        asset_snapshot=snapshot,
        asset_active=True,
        asset_current_snapshot_id=snapshot.snapshot_id,
        asset_fingerprint="c" * 64,
        inputs=inputs,
        scope_watch=build_scope_watch(inputs, snapshot),
        input_digest="d" * 64,
    )
    return AssessmentReceipt(
        assessment_id=str(uuid4()),
        tenant_id=snapshot.tenant_id,
        asset_id=snapshot.asset_id,
        asset_snapshot_id=snapshot.snapshot_id,
        event_id=inputs.rule.event_id,
        rule_id=inputs.rule.rule_id,
        rule_version=1,
        knowledge_epoch=None,
        scope_epoch_map=inputs.scope_epoch_map,
        rule_result=None,
        status="insufficient_evidence",
        freshness="unknown",
        missing_requirements=("unsupported_rule",),
        conflicts=(),
        limitations=("synthetic-unit-fixture",),
        exposure_result="not_evaluated",
        prepared=prepared,
        input_digest=prepared.input_digest,
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
    )
