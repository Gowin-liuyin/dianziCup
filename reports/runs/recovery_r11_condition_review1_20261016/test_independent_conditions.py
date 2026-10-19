"""Synthetic independent review probes; these are not product gold labels."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ai_intel.assessment.conditions import (
    ConditionFact,
    ConditionInputError,
    EvidenceReference,
    condition_digest,
    evaluate_condition_tree,
    parse_condition_tree,
)
from ai_intel.assessment.rules import (
    DEFINED_PREDICATES,
    ConditionRule,
    RuleLeafSupport,
    RuleValidationPolicy,
    evaluate_rule,
    validate_rule,
)
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.domain.access import AccessScope, Role

SCOPE = AccessScope.for_authenticated_user("review-user", "review-tenant", Role.ANALYST)
STAMP = datetime(2026, 10, 16, tzinfo=UTC)


def inventory(**updates):
    fields = dict(
        schema_version="r11-asset-candidate-1", snapshot_id="review-snapshot",
        asset_id="review-asset", tenant_id="review-tenant", snapshot_number=1,
        observed_at=STAMP, recorded_at=STAMP, source_kind="fixture_manifest",
        inventory_completeness="partial", declared_scope=("runtime",), components=(),
        configuration=(), tool_permissions=None, input_channels=None, network_exposure=None,
        snapshot_sha256="1" * 64,
    )
    fields.update(updates)
    return AssetSnapshotResponse.model_validate(fields)


def condition(**updates):
    fields = dict(node_id="configuration", kind="configuration_equals", field="trust_remote_code", expected=True)
    fields.update(updates)
    return parse_condition_tree(fields)


def span(**updates):
    quote = "部署缓解"
    fields = dict(
        evidence_id="review-span", source_id="review-source", document_id="review-document",
        revision_id="review-revision", block_id="review-block", start_offset=2,
        end_offset=2 + len(quote), quote_text=quote,
        quote_sha256=hashlib.sha256(quote.encode()).hexdigest(), scope={"visibility": "public"},
        support_kind="supports", validation_status="validated",
    )
    fields.update(updates)
    return EvidenceReference.model_validate(fields)


def mitigation_fact(**updates):
    fields = dict(
        claim_id="review-claim", asset_snapshot_id="review-snapshot", mitigation_key="approval",
        value=True, claim_status="supported", claim_origin="human_confirmed",
        condition_scope="observed_path", scope={"visibility": "public"}, source_id="review-source",
        document_id="review-document", source_revision_id="review-revision", evidence=(span(),),
    )
    fields.update(updates)
    return ConditionFact.model_validate(fields)


def rule(node=None, **updates):
    fields = dict(
        rule_id="review-rule", version=1, event_id="review-event", rule_kind="software_applicability",
        condition_ast=node if node is not None else condition(), supporting_claim_ids=("review-claim",),
        source_span_ids=("review-span",), scope={"visibility": "public"}, status="candidate",
    )
    fields.update(updates)
    return ConditionRule.model_validate(fields)


def leaf_support(node=None, **updates):
    node = node if node is not None else condition()
    fields = dict(
        node_id=node.node_id, condition_sha256=condition_digest(node), claim_id="review-claim",
        claim_status="supported", claim_origin="source_explicit", condition_scope="software_applicability",
        source_id="review-source", document_id="review-document", source_revision_id="review-revision",
        scope={"visibility": "public"}, evidence=(span(),), necessary_condition_supported=True,
        range_completeness_confirmed=False,
    )
    fields.update(updates)
    return RuleLeafSupport.model_validate(fields)


def validation(candidate, supports=None, automatic=True):
    return validate_rule(candidate, access_scope=SCOPE, policy=RuleValidationPolicy(
        policy_version="review-policy", approved_predicates=DEFINED_PREDICATES,
        automatic_publication_enabled=automatic,
    ), supports=supports if supports is not None else (leaf_support(candidate.condition_ast),))


@pytest.mark.parametrize("status", ["published", "retired"])
def test_lifecycle_validation_does_not_downgrade_frozen_history(status):
    candidate = rule(status=status, published_at=STAMP, retired_at=STAMP if status == "retired" else None)
    result = validation(candidate)
    assert result.resulting_status == status
    assert candidate.status == status
    if status == "retired":
        assert not result.eligible
        assert not result.automatic_publication_eligible


@pytest.mark.parametrize("bad_version", [True, "1", 1.0, 0, -1])
def test_rule_version_is_strict_positive_integer(bad_version):
    with pytest.raises(ValidationError):
        rule(version=bad_version)


@pytest.mark.parametrize("binding", ["source_id", "document_id", "revision_id"])
def test_mitigation_cannot_use_detached_source_document_revision(binding):
    node = parse_condition_tree(dict(node_id="mitigation", kind="mitigation_confirmed", mitigation_key="approval"))
    result = evaluate_condition_tree(node, inventory(), access_scope=SCOPE, supporting_facts=(
        mitigation_fact(evidence=(span(**{binding: "wrong"}),)),
    ), rule_kind="observed_path")
    assert result.value == "unknown"
    assert result.missing_requirements == ("mitigation",)


@pytest.mark.parametrize("fact_update", [dict(asset_snapshot_id="old-snapshot"), dict(claim_origin="model_hypothesis"), dict(claim_status="withdrawn"), dict(evidence=(span(support_kind="context"),))])
def test_mitigation_inactive_model_context_and_old_snapshot_do_not_confirm(fact_update):
    node = parse_condition_tree(dict(node_id="mitigation", kind="mitigation_confirmed", mitigation_key="approval"))
    result = evaluate_condition_tree(node, inventory(), access_scope=SCOPE, supporting_facts=(mitigation_fact(**fact_update),), rule_kind="observed_path")
    assert result.value == "unknown"


@pytest.mark.parametrize("operator,decisive,expected", [("all_of", False, "false"), ("any_of", True, "true")])
def test_decisive_parent_retains_source_conflict(operator, decisive, expected):
    tree = parse_condition_tree(dict(node_id="root", kind=operator, children=[
        condition().model_dump(), dict(node_id="mitigation", kind="mitigation_confirmed", mitigation_key="approval"),
    ]))
    result = evaluate_condition_tree(tree, inventory(configuration=(dict(name="trust_remote_code", value=decisive, source_field_locator="/configuration/trust_remote_code"),)), access_scope=SCOPE,
        supporting_facts=(mitigation_fact(claim_status="disputed"),), rule_kind="observed_path")
    assert result.value == expected
    assert result.child_results[1].value == "conflict"
    assert result.observed_conflict_ids == ("review-claim",)
    assert result.evidence_ids == ("review-span",)


def test_support_binds_to_exact_leaf_and_does_not_publish():
    candidate = rule()
    valid = validation(candidate)
    assert valid.eligible and valid.automatic_publication_eligible
    assert valid.resulting_status == "validated" and candidate.status == "candidate"
    changed = rule(condition(expected=False))
    detached = validation(changed, supports=(leaf_support(candidate.condition_ast),))
    assert not detached.eligible
    assert "detached_support:configuration" in detached.missing_requirements
    assert not validation(candidate, automatic=False).automatic_publication_eligible


def test_attached_refutation_blocks_even_when_one_span_supports():
    evidence = (span(), span(evidence_id="refuting-span", support_kind="refutes"))
    result = validation(rule(), supports=(leaf_support(evidence=evidence),))
    assert not result.eligible
    assert "refuted_condition:configuration" in result.conflicts


def test_private_leaf_evidence_cannot_widen_to_public_rule():
    private = {"visibility": "tenant", "tenant_id": "review-tenant"}
    result = validation(rule(), supports=(leaf_support(evidence=(span(scope=private),)),))
    assert not result.eligible
    assert "scope_widening:configuration" in result.conflicts


def test_deep_mutable_version_assertion_is_revalidated_at_evaluation_and_validation():
    node = parse_condition_tree(dict(node_id="version", kind="version_in_range", assertion=dict(
        package_key="fixture", ecosystem="PyPI", scheme="pep440", raw_expression="[1,2)",
        intervals=[dict(introduced="1", fixed="2")], comparison_support="supported"), range_complete=True))
    candidate = rule(node)
    with pytest.raises(ValidationError, match="frozen_instance"):
        node.assertion.intervals[0].last_affected = "3"
    node.assertion.intervals[0].__dict__["last_affected"] = "3"
    with pytest.raises(ValidationError):
        evaluate_condition_tree(node, inventory(), access_scope=SCOPE)
    with pytest.raises(ValidationError):
        validation(candidate)


def test_json_size_and_scalar_budget_reject_before_any_approval():
    with pytest.raises(ValueError, match="JSON body outside limit"):
        parse_condition_tree(" " * (16 * 1024 * 1024 + 1))
    raw = dict(node_id="root", kind="all_of", children=[condition().model_dump()], extra=["x"] * 50001)
    with pytest.raises(ValueError, match="JSON structure outside limit"):
        parse_condition_tree(json.dumps(raw))


def test_rule_kind_separates_network_path_from_software_and_research_execution():
    network = parse_condition_tree(dict(node_id="network", kind="network_reachable", field="public_endpoint"))
    snapshot = inventory(network_exposure=(dict(name="public_endpoint", value=False, source_field_locator="/network_exposure/public_endpoint"),))
    software = evaluate_condition_tree(network, snapshot, access_scope=SCOPE)
    observed = evaluate_rule(rule(network, status="published", published_at=STAMP, rule_kind="observed_path"), snapshot, access_scope=SCOPE)
    assert software.value == "unknown" and observed.evaluation_tree.value == "false"
    assert observed.rule_kind == "observed_path"
    assert "observed_path_does_not_change_software_fix_status" in observed.limitations
    research = evaluate_rule(rule(condition(), status="published", published_at=STAMP, rule_kind="research_prerequisites"), inventory(configuration=(dict(name="trust_remote_code", value=True, source_field_locator="/configuration/trust_remote_code"),)), access_scope=SCOPE)
    assert research.status == "supported_applicability"
    assert "research_prerequisites_do_not_confirm_execution_success" in research.limitations


def test_partial_inventory_empty_component_is_unknown():
    absent = parse_condition_tree(dict(node_id="absence", kind="inventory_proves_absence", package_key="review-package", ecosystem="PyPI", declared_scope="runtime"))
    assert evaluate_condition_tree(absent, inventory(), access_scope=SCOPE).value == "unknown"
    assert evaluate_condition_tree(absent, inventory(inventory_completeness="complete_for_declared_scope"), access_scope=SCOPE).value == "true"


def test_duplicate_json_key_rejects_never_evaluates_arbitrary_expression():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        parse_condition_tree('{"node_id":"root","kind":"all_of","kind":"eval","children":[]}')


def test_invalid_direct_shared_ast_mapping_is_rejected():
    child = condition().model_dump()
    with pytest.raises(ConditionInputError, match="cycle_or_shared_node"):
        parse_condition_tree(dict(node_id="root", kind="all_of", children=[child, child]))
