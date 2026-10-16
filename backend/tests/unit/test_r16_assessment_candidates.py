"""Explicit isolated fixtures test observable union and signed continuation behavior."""

import base64
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from tests.unit.test_r11_pg_assessment_scope import candidate_inputs

from ai_intel.assessment.assessment_service import build_scope_watch
from ai_intel.assessment.persistence_contracts import AssessmentReceipt, PreparedAssessment
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.revalidation.candidate_contracts import CandidateContinuation
from ai_intel.revalidation.candidates import (
    AffectedAssessmentScope,
    CandidateDiscoveryError,
    _decode_cursor,
    _encode_cursor,
    _references,
    _signing_bytes,
    candidate_reasons,
    rule_package_keys,
)

SYNTHETIC_KEY = SecretStr("01" * 32)


def snapshot(*, components=(), completeness="unknown"):
    return AssetSnapshotResponse.model_validate(
        dict(
            schema_version="r11-asset-candidate-1",
            snapshot_id="fixture-snapshot",
            asset_id="fixture-asset",
            tenant_id="fixture-tenant",
            snapshot_number=1,
            observed_at=datetime(2026, 10, 16, tzinfo=UTC),
            recorded_at=datetime(2026, 10, 16, tzinfo=UTC),
            source_kind="fixture",
            inventory_completeness=completeness,
            declared_scope=(),
            components=components,
            configuration=(),
            tool_permissions=None,
            input_channels=None,
            network_exposure=None,
            snapshot_sha256="b" * 64,
        )
    )


def component(package="not-in-inventory", *, purl=None, ecosystem="PyPI"):
    return dict(
        component_id="fixture-component",
        ecosystem=ecosystem,
        package_name=package,
        display_name=None,
        purl=purl,
        version=None,
        version_scheme="pep440",
        image_digest=None,
        dependency_path=None,
        source_field_locator="/components/0",
    )


def receipt():
    inputs = candidate_inputs()
    asset = snapshot()
    watch = build_scope_watch(inputs, asset)
    prepared = PreparedAssessment(
        preparation_receipt_id="fixture-preparation",
        actor_user_id="fixture-user",
        actor_role="analyst",
        permission_version=1,
        asset_snapshot=asset,
        asset_active=True,
        asset_current_snapshot_id=asset.snapshot_id,
        asset_fingerprint="b" * 64,
        inputs=inputs,
        scope_watch=watch,
        input_digest="a" * 64,
    )
    result = AssessmentReceipt(
        assessment_id="fixture-assessment",
        tenant_id=asset.tenant_id,
        asset_id=asset.asset_id,
        asset_snapshot_id=asset.snapshot_id,
        event_id=inputs.rule.event_id,
        rule_id=inputs.rule.rule_id,
        rule_version=1,
        knowledge_epoch=0,
        scope_epoch_map=inputs.scope_epoch_map,
        rule_result=None,
        status="insufficient_evidence",
        freshness="stale",
        missing_requirements=("unsupported_rule",),
        conflicts=(),
        limitations=(),
        exposure_result="not_evaluated",
        prepared=prepared,
        input_digest="a" * 64,
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
    )
    return result, watch


def cursor():
    return CandidateContinuation(
        change_id="fixture-change",
        scope_key="public",
        actor_user_id="fixture-user",
        tenant_id="fixture-tenant",
        actor_role="analyst",
        permission_version=1,
        requested_epoch=2,
        scope_epoch_map={"public": 2, "tenant:fixture-tenant": None},
        query_fingerprint="a" * 64,
        partition_fingerprint="b" * 32,
        limit=20,
        after_asset_id="fixture-asset",
        after_kind="asset",
        after_reference_id="fixture-asset",
    )


def test_old_dependency_and_explicit_empty_scope_are_both_retained():
    result, watch = receipt()
    affected = AffectedAssessmentScope(
        frozenset((result.rule_id,)), rule_ids=frozenset((result.rule_id,))
    )
    assert candidate_reasons(affected, snapshot(), result, watch) == (
        "empty_rule_scope",
        "old_dependency",
        "scope_watch",
    )


@pytest.mark.parametrize("change", ["expanded", "shrunk", "withdrawn", "replayed", "out_of_order"])
def test_scope_change_keeps_previously_excluded_and_unknown_results(change):
    result, watch = receipt()
    affected = AffectedAssessmentScope(
        frozenset(), package_keys=frozenset(("PyPI:not-in-inventory",))
    )
    assert "scope_watch" in candidate_reasons(affected, snapshot(), result, watch)
    assert result.freshness.value == "stale" and result.rule_result is None


def test_missing_watch_cannot_produce_false_empty_candidate_set():
    result, _ = receipt()
    assert candidate_reasons(AffectedAssessmentScope(frozenset()), snapshot(), result) == (
        "missing_scope_watch",
    )


def test_unknown_epoch_still_enters_partition_fallback():
    result, watch = receipt()
    watch = watch.model_copy(update={"scope_epoch_map": {"public": None}})
    assert candidate_reasons(AffectedAssessmentScope(frozenset()), snapshot(), result, watch) == (
        "empty_rule_scope",
        "partition_fallback",
    )


@pytest.mark.parametrize(
    "package,purl", [("not-in-inventory", None), ("different-name", "pkg:pypi/demo")]
)
def test_current_package_identity_matches_name_or_exact_purl(package, purl):
    identity = purl or package
    affected = AffectedAssessmentScope(frozenset(), package_keys=frozenset(("PyPI:" + identity,)))
    assert candidate_reasons(affected, snapshot(components=(component(package, purl=purl),))) == (
        "new_package_association",
    )


def test_unrelated_complete_inventory_and_other_ecosystem_are_not_exact_matches():
    affected = AffectedAssessmentScope(
        frozenset(), package_keys=frozenset(("PyPI:not-in-inventory",))
    )
    assert (
        candidate_reasons(
            affected,
            snapshot(
                components=(component(ecosystem="npm"),), completeness="complete_for_declared_scope"
            ),
        )
        == ()
    )


def test_missing_component_in_unknown_inventory_is_not_negative_evidence():
    affected = AffectedAssessmentScope(frozenset(), package_keys=frozenset(("PyPI:fixture",)))
    assert candidate_reasons(affected, snapshot()) == ("partition_fallback",)


def test_unknown_change_partitions_even_empty_assets_without_mutation():
    affected = AffectedAssessmentScope(frozenset(), fallback_reason="unknown_change")
    assert candidate_reasons(affected, snapshot()) == ("partition_fallback",)


def test_asset_change_discovers_old_assessment_and_new_current_snapshot():
    result, watch = receipt()
    affected = AffectedAssessmentScope(frozenset(), asset_ids=frozenset(("fixture-asset",)))
    assert "old_dependency" in candidate_reasons(affected, snapshot(), result, watch)
    assert candidate_reasons(affected, snapshot()) == ("new_package_association",)


def test_package_extraction_reuses_actual_rule_identity():
    assert rule_package_keys(candidate_inputs().rule) == frozenset(("PyPI:not-in-inventory",))


def test_cursor_round_trip_preserves_null_epochs_and_position():
    key = _signing_bytes(SYNTHETIC_KEY)
    value = _encode_cursor(cursor(), key)
    assert _decode_cursor(value, key) == cursor()


@pytest.mark.parametrize(
    "mode", ["signature", "position", "wrong_key", "oversized", "invalid_base64"]
)
def test_cursor_rejects_tamper_and_unbounded_payload(mode):
    key = _signing_bytes(SYNTHETIC_KEY)
    value = _encode_cursor(cursor(), key)
    if mode == "signature":
        raw = bytearray(base64.urlsafe_b64decode(value))
        raw[0] ^= 1
        value = base64.urlsafe_b64encode(raw).decode()
    elif mode == "position":
        raw = base64.urlsafe_b64decode(value).replace(b"fixture-asset", b"another-asset")
        value = base64.urlsafe_b64encode(raw).decode()
    elif mode == "wrong_key":
        key = bytes(32)
    elif mode == "oversized":
        value = "x" * 4097
    else:
        value = "!"
    with pytest.raises(CandidateDiscoveryError, match="cursor_invalid"):
        _decode_cursor(value, key)


@pytest.mark.parametrize(
    "value", [None, SecretStr("a" * 63), SecretStr("A" * 64), SecretStr("g" * 64)]
)
def test_cursor_key_is_server_configured_fixed_hex_and_never_printed(value):
    with pytest.raises(
        CandidateDiscoveryError, match=r"signing_key_(not_configured|invalid)"
    ) as failure:
        _signing_bytes(value)
    assert "a" * 63 not in str(failure.value)


def test_reference_extraction_preserves_private_source_parent_fields():
    refs = _references(
        dict(
            claims=[
                dict(
                    source_id={"value": "source"},
                    source_revision_id={"value": "revision"},
                    evidence_links=[dict(evidence_id={"value": "span"})],
                )
            ],
            rule_id="rule",
        )
    )
    assert refs["source"] == {"source"} and refs["revision"] == {"revision"}
    assert refs["evidence"] == {"span"} and refs["rule"] == {"rule"}


def test_change_reference_budget_fails_explicitly():
    with pytest.raises(CandidateDiscoveryError, match="reference_budget_exceeded"):
        _references(dict(source_ids=[str(index) for index in range(257)]))
