"""Observable scope descriptions retain prior empty rule ranges without inventing matches."""

import pytest
from pydantic import ValidationError

from ai_intel.assessment.assessment_service import build_scope_watch
from ai_intel.assessment.conditions import parse_condition_tree
from ai_intel.assessment.persistence_contracts import AssessmentScopeWatch, RuleInputSnapshot
from ai_intel.assessment.rule_persistence import SERVER_RULE_VALIDATION_POLICY
from ai_intel.assessment.rules import ConditionRule, validate_rule
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.domain.access import AccessScope, Role


def candidate_inputs():
    rule = ConditionRule(
        rule_id="fixture-rule",
        version=1,
        event_id="fixture-event",
        rule_kind="software_applicability",
        condition_ast=parse_condition_tree(
            dict(
                node_id="component",
                kind="component_matches",
                ecosystem="PyPI",
                package_key="not-in-inventory",
            )
        ),
        supporting_claim_ids=(),
        source_span_ids=(),
        scope=dict(visibility="tenant", tenant_id="fixture-tenant"),
        status="candidate",
    )
    validation = validate_rule(
        rule,
        access_scope=AccessScope.for_authenticated_user(
            "fixture-user", "fixture-tenant", Role.ANALYST
        ),
        policy=SERVER_RULE_VALIDATION_POLICY,
        supports=(),
    )
    return RuleInputSnapshot(
        rule=rule,
        author_user_id="fixture-author",
        event_version=1,
        event_status="active",
        sources=(),
        active_revision_ids=(),
        supports=(),
        scope_epoch_map={"public": 0, "tenant:fixture-tenant": 1},
        validation=validation,
        input_digest="a" * 64,
    )


def test_empty_published_rule_scope_still_watches_rule_package_and_event():
    snapshot = AssetSnapshotResponse.model_validate(
        dict(
            schema_version="r11-asset-candidate-1",
            snapshot_id="fixture-snapshot",
            asset_id="fixture-asset",
            tenant_id="fixture-tenant",
            snapshot_number=1,
            observed_at="2026-10-16T00:00:00Z",
            recorded_at="2026-10-16T00:00:00Z",
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
    )
    watch = build_scope_watch(candidate_inputs(), snapshot)
    assert watch.package_keys == ("PyPI:not-in-inventory",)
    assert watch.event_ids == ("fixture-event",)
    assert watch.no_published_rule and watch.selected_rule_ids == ()
    assert watch.scope_epoch_map == {"public": 0, "tenant:fixture-tenant": 1}


@pytest.mark.parametrize(
    "updates",
    [dict(scope_epoch_map={}), dict(no_published_rule=False), dict(scope_epoch_map={"public": -1})],
)
def test_invalid_scope_snapshots_are_rejected(updates):
    payload = dict(
        tenant_id="fixture-tenant",
        event_ids=("fixture-event",),
        package_keys=(),
        rule_id="fixture-rule",
        rule_version=1,
        rule_kind="software_applicability",
        scope_epoch_map={"public": 0},
        selected_rule_ids=(),
        no_published_rule=True,
    )
    payload.update(updates)
    with pytest.raises(ValidationError):
        AssessmentScopeWatch.model_validate(payload)


def test_rule_policy_is_fixed_and_automatic_publication_is_disabled():
    assert SERVER_RULE_VALIDATION_POLICY.policy_version == "r11-pg-review-policy-1"
    assert not SERVER_RULE_VALIDATION_POLICY.automatic_publication_enabled


def test_missing_epoch_remains_null_in_typed_scope_snapshot():
    watch = AssessmentScopeWatch(
        tenant_id="fixture-tenant",
        event_ids=("fixture-event",),
        package_keys=(),
        rule_id="fixture-rule",
        rule_version=1,
        rule_kind="software_applicability",
        scope_epoch_map={"public": None, "tenant:fixture-tenant": 1},
        selected_rule_ids=(),
        no_published_rule=True,
    )
    assert watch.model_dump(mode="json")["scope_epoch_map"]["public"] is None


def test_watch_preserves_existing_manifest_package_limits():
    long_key = "PyPI:" + "p" * 4096
    packages = (long_key, *("PyPI:package-" + str(index) for index in range(128)))
    watch = AssessmentScopeWatch(
        tenant_id="fixture-tenant",
        event_ids=("fixture-event",),
        package_keys=packages,
        rule_id="fixture-rule",
        rule_version=1,
        rule_kind="software_applicability",
        scope_epoch_map={"public": None},
        selected_rule_ids=(),
        no_published_rule=True,
    )
    assert len(watch.package_keys) == 129 and watch.package_keys[0] == long_key
