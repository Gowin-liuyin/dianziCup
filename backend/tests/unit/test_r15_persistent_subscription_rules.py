"""Offline behavior tests; AccessScope fixtures grant no PostgreSQL authentication claim."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_r15_composite_receipt_policy import evaluated_receipt

from ai_intel.domain.access import AccessScope, Role
from ai_intel.recommendations.candidate_loader import (
    CandidateLoader,
    LoadedCandidates,
    assessment_material,
)
from ai_intel.recommendations.service import (
    generation_input_digest,
    require_version,
    verify_payload,
)
from ai_intel.recommendations.service_contracts import (
    RecommendationIntegrityError,
    SubscriptionRecord,
    SubscriptionSpec,
    canonical_json_bytes,
    content_sha256,
)

NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)


def subscription_record(**changes):
    spec = changes.get("spec", SubscriptionSpec(product_keys=("PyPI:alpha",)))
    values = dict(
        subscription_id=uuid4(),
        tenant_id="fixture-owner",
        user_id="fixture-user",
        version=1,
        spec=spec,
        spec_sha256=content_sha256(spec.model_dump(mode="json")),
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return SubscriptionRecord(**values)


def test_canonical_json_is_stable_unicode_bytes_and_not_default_repr():
    assert (
        canonical_json_bytes({"β": [True, None], "a": "中文"})
        == '{"a":"中文","β":[true,null]}'.encode()
    )
    assert content_sha256({"a": 1, "b": 2}) == content_sha256({"b": 2, "a": 1})
    with pytest.raises(TypeError):
        canonical_json_bytes(uuid4())


@pytest.mark.parametrize(
    "invalid", [float("nan"), float("inf"), {1: "converted-key"}, {"nested": [{False: 1}]}]
)
def test_non_json_values_are_rejected(invalid):
    with pytest.raises(ValueError):
        canonical_json_bytes(invalid)


def test_integrity_mismatch_never_returns_empty_success():
    payload = {"value": "old"}
    verify_payload(payload, content_sha256(payload))
    with pytest.raises(RecommendationIntegrityError, match="hash_mismatch"):
        verify_payload({"value": "new"}, content_sha256(payload))


@pytest.mark.parametrize("invalid", [True, False, 0, -1, "1", 1.0, None])
def test_subscription_cas_version_requires_strict_positive_integer(invalid):
    with pytest.raises(ValueError, match="version_invalid"):
        require_version(invalid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("enabled", 1),
        ("maximum_priority_bucket", True),
        ("maximum_priority_bucket", -1),
        ("maximum_priority_bucket", 4),
        ("tenant_id", "body-tenant"),
        ("user_id", "body-user"),
        ("validated", True),
    ],
)
def test_spec_rejects_permissions_and_malformed_filters(field, value):
    with pytest.raises(ValidationError):
        SubscriptionSpec.model_validate({"product_keys": ["PyPI:alpha"], field: value})


def test_spec_requires_distinct_explicit_interests_and_policy_adapter_owner():
    with pytest.raises(ValidationError):
        SubscriptionSpec()
    with pytest.raises(ValidationError):
        SubscriptionSpec(product_keys=("x", "x"))
    record = subscription_record()
    adapted = record.policy_subscription()
    assert (adapted.user_id, adapted.tenant_id, adapted.product_keys) == (
        record.user_id,
        record.tenant_id,
        record.spec.product_keys,
    )


def test_generation_fence_includes_epoch_actor_spec_cutoff_and_budget():
    record = subscription_record()
    scope = AccessScope.for_authenticated_user(record.user_id, record.tenant_id, Role.ANALYST)
    loaded = LoadedCandidates((), (), {"public": 2}, "a" * 64, False)
    original = generation_input_digest(record, scope, loaded, NOW, (), 200, ())
    changed = [
        generation_input_digest(
            record,
            scope,
            LoadedCandidates((), (), {"public": 3}, "a" * 64, False),
            NOW,
            (),
            200,
            (),
        ),
        generation_input_digest(record, scope, loaded, NOW + timedelta(seconds=1), (), 200, ()),
        generation_input_digest(record, scope, loaded, NOW, (), 199, ()),
        generation_input_digest(
            record,
            AccessScope.for_authenticated_user(record.user_id, record.tenant_id, Role.VIEWER),
            loaded,
            NOW,
            (),
            200,
            (),
        ),
        generation_input_digest(
            record.model_copy(update={"version": 2}), scope, loaded, NOW, (), 200, ()
        ),
    ]
    assert all(value != original for value in changed)


def test_material_does_not_change_for_read_clock_receipt_identity_or_global_epoch():
    receipt = evaluated_receipt()
    changed_inputs = receipt.prepared.inputs.model_copy(
        update={"scope_epoch_map": {"public": 900}, "input_digest": "9" * 64}
    )
    changed = receipt.model_copy(
        update={
            "assessment_id": "new-receipt",
            "created_at": NOW,
            "knowledge_epoch": 900,
            "scope_epoch_map": {"public": 900},
            "input_digest": "8" * 64,
            "prepared": receipt.prepared.model_copy(
                update={"inputs": changed_inputs, "preparation_receipt_id": "new-prepare"}
            ),
        }
    )
    assert assessment_material(receipt) == assessment_material(changed)
    material = assessment_material(receipt)
    assert material["supports"] and material["result"]


@pytest.mark.parametrize("configuration", [True, False, None])
def test_material_preserves_actual_composite_four_state_and_support(configuration):
    receipt = evaluated_receipt(configuration=configuration)
    material = assessment_material(receipt)
    assert material["status"] == receipt.status.value
    assert material["missing"] == receipt.missing_requirements
    assert material["conflicts"] == receipt.conflicts
    assert all(item["evidence"]["evidence_id"] for item in material["supports"])


def test_disabled_loader_is_an_explicit_stop_without_io():
    class ForbiddenIO:
        def execute(self, *args, **kwargs):
            raise AssertionError("disabled loader read PG")

    scope = AccessScope.for_authenticated_user("fixture-user", "fixture-owner", Role.VIEWER)
    loader = CandidateLoader(ForbiddenIO(), scope, None, None, "fixture")
    record = subscription_record(spec=SubscriptionSpec(product_keys=("x",), enabled=False))
    loaded = loader.load(record, (), NOW)
    assert loaded.events == () and loaded.gaps == () and loaded.partial is False
    assert loaded.facts_sha256 == content_sha256({"disabled": True})
    with pytest.raises(ValueError, match="budget_or_identity"):
        loader.load(record, (uuid4(),) * 2, NOW)
    with pytest.raises(ValueError, match="budget_or_identity"):
        loader.load(record, tuple(uuid4() for _ in range(2001)), NOW)


@pytest.mark.parametrize(
    "role,expected",
    [
        (Role.VIEWER, ("public",)),
        (Role.ANALYST, ("public", "tenant:fixture-owner")),
        (Role.TENANT_ADMIN, ("public", "tenant:fixture-owner")),
    ],
)
def test_knowledge_scope_epochs_do_not_expose_unreadable_tenant_counters(role, expected):
    scope = AccessScope.for_authenticated_user("fixture-user", "fixture-owner", role)
    loader = CandidateLoader(None, scope, None, None, "fixture")
    assert loader._scope_keys() == expected
