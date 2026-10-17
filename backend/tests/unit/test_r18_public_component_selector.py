"""Explicit fixture-only selection tests; service doubles are not live PostgreSQL proof."""

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from tests.unit.test_public_write_adapters import fixture_receipt, fixture_request, fixture_services

from ai_intel.api.public_component_selector import (
    MAX_COMPONENT_SELECTION_CANDIDATES,
    SELECTION_LIMITATIONS,
    select_current_component_assessments,
)
from ai_intel.api.public_write_adapters import PublicWriteMappingError, stack_current_assessments
from ai_intel.assessment.conditions import parse_condition_tree
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.enums import AssessmentStatus


def selection_fixture(*receipts):
    assessment, knowledge = fixture_services(receipts[0] if receipts else fixture_receipt())
    assessment.engine = object()
    knowledge.session.in_transaction.return_value = True
    knowledge.session.connection.return_value.engine = assessment.engine
    knowledge.session.scalars.return_value.all.return_value = [
        receipt.assessment_id for receipt in receipts
    ]
    assessment.read_in_session.side_effect = receipts
    return assessment, knowledge


def updated_components(receipt, **updates):
    component = receipt.prepared.asset_snapshot.components[0].model_copy(update=updates)
    snapshot = receipt.prepared.asset_snapshot.model_copy(update={"components": (component,)})
    return receipt.model_copy(
        update={"prepared": receipt.prepared.model_copy(update={"asset_snapshot": snapshot})}
    )


def test_unique_current_selection_uses_same_transaction_and_tenant_bound_jsonb_query():
    receipt = fixture_receipt()
    assessment, knowledge = selection_fixture(receipt)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (UUID(receipt.assessment_id),)
    assert selection.reason_codes == ("selected_current_assessment",)
    assert selection.limitations == SELECTION_LIMITATIONS
    assessment.read_in_session.assert_called_once_with(
        knowledge.session, knowledge.scope, receipt.assessment_id
    )
    query = knowledge.session.scalars.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "assets.current_snapshot_id = asset_snapshots.snapshot_id" in str(query)
    assert "assessment_results.tenant_id = asset_snapshots.tenant_id" in str(query)
    assert "assessment_results.tenant_id =" in str(query)
    assert "@>" in str(query)
    assert knowledge.scope.tenant_id in query.params.values()
    assert [{"ecosystem": "PyPI", "package_name": "fixture", "version": "1.0"}] in (
        query.params.values()
    )


@pytest.mark.parametrize("status", list(AssessmentStatus))
def test_single_current_candidate_preserves_each_existing_assessment_state(status):
    receipt = fixture_receipt(status)
    assessment, knowledge = selection_fixture(receipt)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (UUID(receipt.assessment_id),)


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"version": None}, "missing_version"),
        ({"version": "invalid version"}, "invalid_version"),
        ({"ecosystem": "Maven"}, "unsupported_ecosystem"),
        ({"purl": "malformed"}, "invalid_purl"),
        ({"purl": "pkg:npm/fixture@1.0.0"}, "component_purl_identity_mismatch"),
        ({"purl": "pkg:pypi/other@1.0"}, "component_purl_identity_mismatch"),
        ({"purl": "pkg:pypi/fixture@2.0"}, "component_purl_version_mismatch"),
        (
            {"purl": "pkg:pypi/fixture@1.0?repository_url=https://example.test"},
            "unsupported_purl_features",
        ),
    ],
)
def test_unknown_or_inconsistent_request_identity_remains_unknown_without_candidate_io(
    updates, reason
):
    assessment, knowledge = selection_fixture(fixture_receipt())
    selection = select_current_component_assessments(
        fixture_request(**updates), assessment, knowledge
    )
    assert selection.assessment_ids == (None,)
    assert selection.reason_codes == (reason,)
    assert reason in selection.limitations
    knowledge.session.scalars.assert_not_called()
    assessment.read_in_session.assert_not_called()


def test_missing_selection_projects_insufficient_evidence_instead_of_safe():
    assessment, knowledge = selection_fixture()
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,)
    assert selection.reason_codes == ("no_match",)
    result = stack_current_assessments(
        fixture_request(), selection.assessment_ids, assessment, knowledge
    )
    assert result.results[0].status == "insufficient_evidence"
    assert result.results[0].freshness == "unknown" and result.results[0].citations == ()


@pytest.mark.parametrize("freshness", ["stale", "unknown"])
def test_database_current_column_cannot_override_shared_currentness_recheck(freshness):
    assessment, knowledge = selection_fixture(fixture_receipt(freshness=freshness))
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,)
    assert selection.reason_codes == (
        "assessment_stale" if freshness == "stale" else "unknown_freshness",
    )


@pytest.mark.parametrize(
    "updates", [{"version": "2.0"}, {"package_name": "other"}, {"ecosystem": "npm"}]
)
def test_changed_receipt_binding_is_an_error_instead_of_no_match(updates):
    assessment, knowledge = selection_fixture(updated_components(fixture_receipt(), **updates))
    with pytest.raises(PublicWriteMappingError, match="component_assessment_binding_mismatch"):
        select_current_component_assessments(fixture_request(), assessment, knowledge)


def test_inconsistent_manifest_purl_is_not_borrowed_as_component_fact():
    receipt = updated_components(fixture_receipt(), purl="pkg:pypi/other@1.0")
    assessment, knowledge = selection_fixture(receipt)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,)
    assert selection.reason_codes == ("component_purl_identity_mismatch",)


def test_semantically_equal_purl_version_is_validated_without_rewriting_snapshot_version():
    receipt = updated_components(fixture_receipt(), purl="pkg:pypi/fixture@1.0.0")
    assessment, knowledge = selection_fixture(receipt)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (UUID(receipt.assessment_id),)


def test_mixed_version_whole_asset_result_is_not_selected_for_one_component():
    receipt = fixture_receipt()
    snapshot = receipt.prepared.asset_snapshot
    snapshot = snapshot.model_copy(
        update={
            "components": (
                *snapshot.components,
                snapshot.components[0].model_copy(update={"version": "2.0"}),
            )
        }
    )
    receipt = receipt.model_copy(
        update={"prepared": receipt.prepared.model_copy(update={"asset_snapshot": snapshot})}
    )
    assessment, knowledge = selection_fixture(receipt)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,) and selection.reason_codes == ("unsupported_rule",)


def test_asset_configuration_predicate_does_not_become_component_confirmation():
    receipt = fixture_receipt()
    rule = receipt.prepared.inputs.rule.model_copy(
        update={
            "condition_ast": parse_condition_tree(
                {
                    "kind": "all_of",
                    "node_id": "root",
                    "children": [
                        {
                            "kind": "component_matches",
                            "node_id": "package",
                            "ecosystem": "PyPI",
                            "package_key": "fixture",
                        },
                        {
                            "kind": "configuration_equals",
                            "node_id": "config",
                            "field": "trust_remote_code",
                            "expected": True,
                        },
                    ],
                }
            )
        }
    )
    receipt = receipt.model_copy(
        update={
            "prepared": receipt.prepared.model_copy(
                update={"inputs": receipt.prepared.inputs.model_copy(update={"rule": rule})}
            )
        }
    )
    assessment, knowledge = selection_fixture(receipt)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,)
    assert selection.reason_codes == ("unsupported_component_rule",)


@pytest.mark.parametrize("second_status", list(AssessmentStatus))
def test_multiple_current_candidates_never_choose_latest_or_excluded_first(second_status):
    first = fixture_receipt(AssessmentStatus.EXCLUDED_WITH_EVIDENCE)
    second = fixture_receipt(second_status).model_copy(update={"assessment_id": str(UUID(int=501))})
    assessment, knowledge = selection_fixture(first, second)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,)
    assert selection.reason_codes == ("ambiguous_current_assessments",)


def test_unique_current_candidate_with_unresolved_stale_candidate_stays_incomplete():
    current = fixture_receipt()
    stale = fixture_receipt(freshness="stale").model_copy(
        update={"assessment_id": str(UUID(int=501))}
    )
    assessment, knowledge = selection_fixture(current, stale)
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,) and selection.reason_codes == ("assessment_stale",)


def test_candidate_bound_does_not_claim_no_match_from_truncated_search():
    assessment, knowledge = selection_fixture()
    knowledge.session.scalars.return_value.all.return_value = ["unused"] * (
        MAX_COMPONENT_SELECTION_CANDIDATES + 1
    )
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    assert selection.assessment_ids == (None,)
    assert selection.reason_codes == ("component_candidate_limit_exceeded",)
    assessment.read_in_session.assert_not_called()


@pytest.mark.parametrize("error", [CrossTenantAccessError, PermissionDeniedError, RuntimeError])
def test_acl_expiry_or_service_failure_is_not_swallowed_as_empty_success(error):
    assessment, knowledge = selection_fixture(fixture_receipt())
    assessment.read_in_session.side_effect = error("fixed-test-reason")
    with pytest.raises(error):
        select_current_component_assessments(fixture_request(), assessment, knowledge)


@pytest.mark.parametrize(
    "role,tenant", [(Role.VIEWER, "fixture-tenant"), (Role.SYSTEM_ADMIN, None)]
)
def test_permission_or_missing_tenant_rejects_before_queries(role, tenant):
    assessment, knowledge = selection_fixture()
    knowledge.scope = AccessScope.for_authenticated_user("unit-owner", tenant, role)
    with pytest.raises(PermissionDeniedError):
        select_current_component_assessments(fixture_request(), assessment, knowledge)
    knowledge.session.scalars.assert_not_called()


@pytest.mark.parametrize("open_transaction,same_engine", [(False, True), (True, False)])
def test_selection_requires_existing_transaction_on_assessment_engine(
    open_transaction, same_engine
):
    assessment, knowledge = selection_fixture()
    knowledge.session.in_transaction.return_value = open_transaction
    if not same_engine:
        knowledge.session.connection.return_value.engine = object()
    with pytest.raises(ValueError, match="caller-owned assessment transaction"):
        select_current_component_assessments(fixture_request(), assessment, knowledge)
    knowledge.session.scalars.assert_not_called()


def test_duplicate_request_indices_and_empty_request_preserve_input_count():
    receipt = fixture_receipt()
    assessment, knowledge = selection_fixture(receipt)
    assessment.read_in_session.side_effect = None
    assessment.read_in_session.return_value = receipt
    payload = fixture_request().model_copy(
        update={"components": fixture_request().components * 200}
    )
    selection = select_current_component_assessments(payload, assessment, knowledge)
    assert selection.assessment_ids == (UUID(receipt.assessment_id),) * 200
    assert selection.reason_codes == ("selected_current_assessment",) * 200
    empty = payload.model_copy(update={"components": ()})
    assert select_current_component_assessments(empty, assessment, knowledge).assessment_ids == ()
