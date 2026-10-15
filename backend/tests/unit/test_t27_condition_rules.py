"""Explicit synthetic fixtures for the W06 pure slice; no product gold labels."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import product

import pytest
from pydantic import ValidationError

from ai_intel.assessment.conditions import (
    ConditionFact,
    EvidenceReference,
    combine_condition_values,
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
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role

FIXTURE_SCOPE = AccessScope.for_authenticated_user("fixture-user", "fixture-tenant", Role.ANALYST)
STAMP = datetime(2026, 10, 16, tzinfo=UTC)


def snapshot(**updates):
    payload = dict(
        schema_version="r11-asset-candidate-1",
        snapshot_id="fixture-snapshot",
        asset_id="fixture-asset",
        tenant_id="fixture-tenant",
        snapshot_number=1,
        observed_at=STAMP,
        recorded_at=STAMP,
        source_kind="fixture_manifest",
        inventory_completeness="partial",
        declared_scope=("PyPI:runtime",),
        components=(),
        configuration=(),
        tool_permissions=None,
        input_channels=None,
        network_exposure=None,
        snapshot_sha256="a" * 64,
    )
    payload.update(updates)
    return AssetSnapshotResponse.model_validate(payload)


def component(version="1.4.1", **updates):
    payload = dict(
        component_id="fixture-component",
        ecosystem="PyPI",
        package_name="fixture",
        display_name="Not an identity",
        purl=None,
        version=version,
        version_scheme="pep440",
        image_digest=None,
        dependency_path=None,
        source_field_locator="/components/0",
    )
    payload.update(updates)
    return payload


def field(name, value, locator="/configuration/0"):
    return dict(name=name, value=value, source_field_locator=locator)


def leaf(kind="configuration_equals", **updates):
    payload = dict(node_id="leaf", kind=kind, field="trust_remote_code", expected=True)
    if kind != "configuration_equals":
        payload = dict(node_id="leaf", kind=kind)
    payload.update(updates)
    return parse_condition_tree(payload)


def version_leaf(**updates):
    payload = dict(
        assertion=dict(
            kind="version_assertion",
            package_key="fixture",
            ecosystem="PyPI",
            scheme="pep440",
            raw_expression="[1.0,1.4.2)",
            intervals=[dict(introduced="1.0", fixed="1.4.2")],
            comparison_support="supported",
        ),
        range_complete=True,
    )
    payload.update(updates)
    return leaf("version_in_range", **payload)


def evidence(**updates):
    payload = dict(
        evidence_id="fixture-span",
        source_id="fixture-source",
        document_id="fixture-document",
        revision_id="fixture-revision",
        block_id="fixture-block",
        start_offset=5,
        end_offset=10,
        quote_text="quote",
        quote_sha256=hashlib.sha256(b"quote").hexdigest(),
        scope=dict(visibility="public"),
        support_kind="supports",
        validation_status="validated",
    )
    payload.update(updates)
    return EvidenceReference.model_validate(payload)


def fact(value=True, **updates):
    payload = dict(
        claim_id="fixture-claim",
        asset_snapshot_id="fixture-snapshot",
        mitigation_key="fixture-mitigation",
        value=value,
        claim_status="supported",
        claim_origin="source_explicit",
        condition_scope="observed_path",
        scope=dict(visibility="public"),
        source_id="fixture-source",
        document_id="fixture-document",
        source_revision_id="fixture-revision",
        evidence=(evidence(),),
    )
    payload.update(updates)
    return ConditionFact.model_validate(payload)


def rule(node=None, **updates):
    payload = dict(
        rule_id="fixture-rule",
        version=1,
        event_id="fixture-event",
        rule_kind="software_applicability",
        condition_ast=node or leaf(),
        supporting_claim_ids=("fixture-claim",),
        source_span_ids=("fixture-span",),
        scope=dict(visibility="public"),
        status="candidate",
    )
    payload.update(updates)
    return ConditionRule.model_validate(payload)


def support(node=None, **updates):
    node = node or leaf()
    payload = dict(
        node_id=node.node_id,
        condition_sha256=condition_digest(node),
        claim_id="fixture-claim",
        claim_status="supported",
        claim_origin="source_explicit",
        condition_scope="software_applicability",
        source_id="fixture-source",
        document_id="fixture-document",
        source_revision_id="fixture-revision",
        scope=dict(visibility="public"),
        evidence=(evidence(),),
        necessary_condition_supported=True,
        range_completeness_confirmed=True,
    )
    payload.update(updates)
    return RuleLeafSupport.model_validate(payload)


def validate(candidate=None, supports=None, **updates):
    policy = RuleValidationPolicy(
        policy_version="fixture-policy",
        approved_predicates=DEFINED_PREDICATES,
        automatic_publication_enabled=True,
    )
    return validate_rule(
        candidate or rule(),
        access_scope=FIXTURE_SCOPE,
        policy=policy,
        supports=(support(),) if supports is None else supports,
        **updates,
    )


def evaluate(node=None, inventory=None, **updates):
    return evaluate_condition_tree(
        node or leaf(), inventory or snapshot(), access_scope=FIXTURE_SCOPE, **updates
    )


@pytest.mark.parametrize(
    ("operator", "left", "right", "expected"),
    [
        (operator, left, right, rows[index][column])
        for operator, rows in (
            (
                "all_of",
                (
                    ("true", "false", "unknown", "conflict"),
                    ("false", "false", "false", "false"),
                    ("unknown", "false", "unknown", "conflict"),
                    ("conflict", "false", "conflict", "conflict"),
                ),
            ),
            (
                "any_of",
                (
                    ("true", "true", "true", "true"),
                    ("true", "false", "unknown", "conflict"),
                    ("true", "unknown", "unknown", "conflict"),
                    ("true", "conflict", "conflict", "conflict"),
                ),
            ),
        )
        for (index, left), (column, right) in product(
            enumerate(("true", "false", "unknown", "conflict")), repeat=2
        )
    ],
)
def test_t27_c01_c02_complete_frozen_truth_tables(operator, left, right, expected):
    assert combine_condition_values(operator, (left, right)) == expected


@pytest.mark.parametrize(
    ("kind", "values", "expected"),
    [
        ("all_of", (False, "conflict"), "false"),
        ("any_of", (True, "conflict"), "true"),
        ("all_of", (True, None), "unknown"),
        ("any_of", (False, None), "unknown"),
    ],
)
def test_t27_c01_c02_preserve_every_child_and_nondecisive_conflict(kind, values, expected):
    children = [
        dict(node_id=f"node{index}", kind="configuration_equals", field=name, expected=True)
        for index, name in enumerate(("trust_remote_code", "authentication_required"))
    ]
    fields = [field("trust_remote_code", values[0])]
    if values[1] == "conflict":
        fields += [
            field("authentication_required", False, "/configuration/1"),
            field("authentication_required", True, "/configuration/2"),
        ]
    else:
        fields.append(field("authentication_required", values[1], "/configuration/1"))
    result = evaluate(
        parse_condition_tree(dict(node_id="root", kind=kind, children=children)),
        snapshot(configuration=fields),
    )
    assert result.value == expected
    assert len(result.child_results) == 2
    assert result.asset_field_refs
    if values[1] == "conflict":
        assert len(result.observed_conflict_ids) == 2
        assert result.child_results[1].value == "conflict"


@pytest.mark.parametrize(
    ("version", "expected"),
    [("1.4.1", "true"), ("1.4.2", "false"), (None, "unknown"), ("invalid", "unknown")],
)
def test_t27_c03_version_engine_fixed_boundary_and_missing(version, expected):
    result = evaluate(version_leaf(), snapshot(components=(component(version),)))
    assert result.value == expected
    assert result.asset_field_refs == ("snapshot:fixture-snapshot:/components/0",)


@pytest.mark.parametrize("completeness", ["partial", "unknown", "complete_for_declared_scope"])
def test_t27_c03_unobserved_component_is_never_version_exclusion(completeness):
    assert (
        evaluate(version_leaf(), snapshot(inventory_completeness=completeness)).value == "unknown"
    )
    assert (
        evaluate(
            leaf("component_matches", ecosystem="PyPI", package_key="fixture"),
            snapshot(inventory_completeness=completeness),
        ).value
        == "unknown"
    )


@pytest.mark.parametrize(
    ("completeness", "scopes", "expected"),
    [
        ("partial", ("PyPI:runtime",), "unknown"),
        ("unknown", ("PyPI:runtime",), "unknown"),
        ("complete_for_declared_scope", ("npm:runtime",), "unknown"),
        ("complete_for_declared_scope", ("PyPI:runtime",), "true"),
    ],
)
def test_t27_c03_absence_requires_exact_complete_scope(completeness, scopes, expected):
    node = leaf(
        "inventory_proves_absence",
        ecosystem="PyPI",
        package_key="fixture",
        declared_scope="PyPI:runtime",
    )
    assert (
        evaluate(node, snapshot(inventory_completeness=completeness, declared_scope=scopes)).value
        == expected
    )
    assert evaluate(node, snapshot(components=(component(),))).value == "false"


@pytest.mark.parametrize("ecosystem", ["Go", "generic", "unsupported", "GIT"])
def test_unsupported_ecosystem_including_ollama_is_not_excluded(ecosystem):
    node = version_leaf(
        assertion=dict(
            package_key="ollama",
            ecosystem=ecosystem,
            scheme="semver",
            raw_expression="[0,1)",
            intervals=[dict(introduced="0", fixed="1.0.0")],
            comparison_support="supported",
        )
    )
    result = evaluate(
        node,
        snapshot(
            components=(
                component(
                    "0.1.0", ecosystem=ecosystem, package_name="ollama", version_scheme="semver"
                ),
            )
        ),
    )
    assert result.value == "unknown"
    assert "unsupported_ecosystem" in result.limitations


def test_exact_identity_accepts_name_or_purl_and_never_display_name_or_other_ecosystem():
    node = leaf("component_matches", ecosystem="PyPI", package_key="fixture")
    assert (
        evaluate(node, snapshot(components=(component(purl="pkg:pypi/fixture"),))).value == "true"
    )
    assert evaluate(node, snapshot(components=(component(ecosystem="npm"),))).value == "unknown"
    assert (
        evaluate(
            node, snapshot(components=(component(package_name="other", display_name="fixture"),))
        ).value
        == "unknown"
    )


def test_multiple_component_versions_preserve_conflicts_and_unknowns():
    components = (
        component(),
        component("1.4.2", component_id="second", source_field_locator="/components/1"),
    )
    result = evaluate(version_leaf(), snapshot(components=components))
    assert result.value == "conflict"
    assert len(result.observed_conflict_ids) == 2
    assert (
        evaluate(version_leaf(), snapshot(components=(component(), component(None)))).value
        == "unknown"
    )


@pytest.mark.parametrize(
    ("kind", "arguments", "inventory", "expected"),
    [
        (
            "component_matches",
            dict(ecosystem="PyPI", package_key="fixture"),
            dict(components=(component(),)),
            "true",
        ),
        (
            "configuration_equals",
            {},
            dict(configuration=(field("trust_remote_code", True),)),
            "true",
        ),
        (
            "permission_includes",
            dict(permission="read_documents"),
            dict(tool_permissions=("read_documents",)),
            "true",
        ),
        (
            "permission_includes",
            dict(permission="read_documents"),
            dict(tool_permissions=()),
            "false",
        ),
        (
            "input_channel_enabled",
            dict(channel="public_api"),
            dict(input_channels=(field("public_api", True),)),
            "true",
        ),
        (
            "network_reachable",
            dict(field="public_endpoint"),
            dict(network_exposure=(field("public_endpoint", False),)),
            "false",
        ),
    ],
)
def test_all_asset_leaf_predicates_read_only_whitelisted_typed_values(
    kind, arguments, inventory, expected
):
    assert (
        evaluate(leaf(kind, **arguments), snapshot(**inventory), rule_kind="observed_path").value
        == expected
    )


@pytest.mark.parametrize(
    ("kind", "arguments"),
    [
        ("configuration_equals", {}),
        ("permission_includes", dict(permission="read_documents")),
        ("input_channel_enabled", dict(channel="public_api")),
        ("network_reachable", dict(field="public_endpoint")),
    ],
)
def test_missing_asset_fields_remain_unknown(kind, arguments):
    result = evaluate(leaf(kind, **arguments), rule_kind="observed_path")
    assert result.value == "unknown"
    assert result.missing_requirements == ("leaf",)


@pytest.mark.parametrize(
    ("status", "origin", "expected"),
    [
        ("supported", "source_explicit", "true"),
        ("supported", "structured_source", "true"),
        ("unverified", "source_explicit", "unknown"),
        ("withdrawn", "source_explicit", "unknown"),
        ("superseded", "source_explicit", "unknown"),
        ("supported", "model_hypothesis", "unknown"),
        ("disputed", "source_explicit", "conflict"),
    ],
)
def test_t27_c05_mitigation_uses_supported_facts_and_keeps_disputes(status, origin, expected):
    result = evaluate(
        leaf("mitigation_confirmed", mitigation_key="fixture-mitigation"),
        supporting_facts=(fact(claim_status=status, claim_origin=origin),),
        rule_kind="observed_path",
    )
    assert result.value == expected
    if expected == "true":
        assert result.evidence_ids == ("fixture-span",)


def test_mitigation_opposing_facts_and_detached_evidence():
    node = leaf("mitigation_confirmed", mitigation_key="fixture-mitigation")
    result = evaluate(
        node, supporting_facts=(fact(), fact(False, claim_id="opposing")), rule_kind="observed_path"
    )
    assert result.value == "conflict"
    assert result.observed_conflict_ids == ("fixture-claim", "opposing")
    for span in (
        evidence(revision_id="detached"),
        evidence(validation_status="unverified"),
        evidence(support_kind="context"),
        evidence(document_id="detached"),
    ):
        assert (
            evaluate(
                node, supporting_facts=(fact(evidence=(span,)),), rule_kind="observed_path"
            ).value
            == "unknown"
        )


def test_valid_rule_returns_versioned_lineage_without_publishing():
    result = validate()
    assert result.eligible and result.automatic_publication_eligible
    assert result.resulting_status == "validated"
    assert result.source_revision_ids == ("fixture-revision",)
    assert result.source_supports[0].document_id == "fixture-document"
    assert result.source_supports[0].evidence[0].start_offset == 5
    assert result.policy_version == "fixture-policy"
    assert result.validator_version == "r11-rule-validator-1"
    assert "pure_validation_requires_transactional_source_recheck" in result.limitations


@pytest.mark.parametrize(
    "changes",
    [
        dict(claim_origin="model_hypothesis"),
        dict(claim_status="unverified"),
        dict(claim_status="disputed"),
        dict(necessary_condition_supported=False),
        dict(condition_sha256="b" * 64),
        dict(source_revision_id="detached"),
        dict(document_id="detached"),
        dict(source_id="detached"),
        dict(evidence=()),
        dict(evidence=(evidence(validation_status="unverified"),)),
        dict(evidence=(evidence(support_kind="refutes"),)),
        dict(condition_scope="research_prerequisites"),
    ],
)
def test_t27_c05_rule_rejects_missing_disputed_model_or_detached_support(changes):
    result = validate(supports=(support(**changes),))
    assert not result.eligible
    assert not result.automatic_publication_eligible
    assert result.missing_requirements or result.conflicts or result.pending_review
    assert result.resulting_status == "candidate"


def test_rule_requires_every_leaf_and_declared_reference_without_allowing_context_substitution():
    tree = parse_condition_tree(
        dict(
            node_id="root",
            kind="all_of",
            children=[
                leaf().model_dump(),
                leaf("permission_includes", node_id="other", permission="read").model_dump(),
            ],
        )
    )
    result = validate(rule(tree))
    assert "unsupported_leaf:other" in result.missing_requirements
    assert not validate(rule(source_span_ids=("detached",))).eligible
    assert not validate(supports=()).eligible


def test_range_completeness_requires_its_own_source_support():
    node = version_leaf()
    result = validate(rule(node), supports=(support(node, range_completeness_confirmed=False),))
    assert "range_completeness_evidence:leaf" in result.missing_requirements


def test_unapproved_defined_predicate_is_pending_review_and_policy_cannot_add_a_dsl():
    policy = RuleValidationPolicy(policy_version="fixture-policy", approved_predicates=frozenset())
    result = validate_rule(rule(), access_scope=FIXTURE_SCOPE, policy=policy, supports=(support(),))
    assert "predicate_not_approved:configuration_equals" in result.pending_review
    with pytest.raises(ValidationError):
        RuleValidationPolicy(policy_version="invalid", approved_predicates=frozenset({"eval"}))


def test_t27_c06_scope_limited_network_and_research_results_do_not_mutate_inventory():
    inventory = snapshot(
        components=(component(),),
        network_exposure=(field("public_endpoint", False),),
        configuration=(field("trust_remote_code", True),),
    )
    network = leaf("network_reachable", field="public_endpoint")
    observed = evaluate_rule(
        rule(network, rule_kind="observed_path", status="published", published_at=STAMP),
        inventory,
        access_scope=FIXTURE_SCOPE,
    )
    assert observed.evaluation_tree.value == "false"
    assert observed.rule_kind == "observed_path"
    assert "observed_path_does_not_change_software_fix_status" in observed.limitations
    assert evaluate(version_leaf(), inventory).value == "true"
    research = evaluate_rule(
        rule(status="published", published_at=STAMP, rule_kind="research_prerequisites"),
        inventory,
        access_scope=FIXTURE_SCOPE,
    )
    assert research.evaluation_tree.value == "true"
    assert "research_prerequisites_do_not_confirm_execution_success" in research.limitations
    assert evaluate(network, inventory).value == "unknown"
    assert not validate(rule(network), supports=(support(network),)).eligible
    assert inventory.components[0].version == "1.4.1"


@pytest.mark.parametrize("status", ["candidate", "validated", "retired"])
def test_rule_lifecycle_never_evaluates_unpublished_or_retired_rules(status):
    candidate = rule(
        status=status,
        published_at=STAMP if status == "retired" else None,
        retired_at=STAMP if status == "retired" else None,
    )
    with pytest.raises(ValueError, match="published"):
        evaluate_rule(candidate, snapshot(), access_scope=FIXTURE_SCOPE)
    if status == "retired":
        assert "retired_rule_requires_new_version" in validate(candidate).pending_review


def test_fixed_snapshot_replay_and_concurrent_evaluation_are_deterministic():
    node, inventory = version_leaf(), snapshot(components=(component(),))
    with ThreadPoolExecutor(max_workers=4) as executor:
        outputs = tuple(executor.map(lambda _: evaluate(node, inventory), range(16)))
    assert all(output == outputs[0] for output in outputs)


def test_private_evidence_cannot_widen_to_public_rule_and_same_tenant_derivation_is_allowed():
    private_scope = dict(visibility="tenant", tenant_id="fixture-tenant")
    private_support = support(scope=private_scope, evidence=(evidence(scope=private_scope),))
    rejected = validate(supports=(private_support,))
    assert not rejected.eligible
    assert "scope_widening:leaf" in rejected.conflicts
    assert validate(rule(scope=private_scope), supports=(private_support,)).eligible


def test_scope_checks_reject_invisible_snapshot_claim_and_evidence_without_sensitive_details():
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        evaluate(inventory=snapshot(tenant_id="hidden-tenant"))
    hidden = dict(visibility="tenant", tenant_id="hidden-tenant")
    for private_support in (support(scope=hidden), support(evidence=(evidence(scope=hidden),))):
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            validate(supports=(private_support,))
    with pytest.raises(PermissionDeniedError):
        evaluate_condition_tree(
            leaf(),
            snapshot(),
            access_scope=AccessScope.for_authenticated_user(
                "viewer", "fixture-tenant", Role.VIEWER
            ),
        )


def test_nondecisive_source_conflict_preserves_all_evidence_and_claim_ids():
    tree = parse_condition_tree(
        dict(
            node_id="root",
            kind="all_of",
            children=[
                leaf().model_dump(),
                leaf(
                    "mitigation_confirmed",
                    node_id="mitigation",
                    mitigation_key="fixture-mitigation",
                ).model_dump(),
            ],
        )
    )
    result = evaluate(
        tree,
        snapshot(configuration=(field("trust_remote_code", False),)),
        supporting_facts=(fact(claim_status="disputed"),),
        rule_kind="observed_path",
    )
    assert result.value == "false"
    assert result.evidence_ids == ("fixture-span",)
    assert result.observed_conflict_ids == ("fixture-claim",)


@pytest.mark.parametrize(
    "changes",
    [dict(quote_sha256="f" * 64), dict(end_offset=11), dict(start_offset=-1), dict(end_offset=5)],
)
def test_evidence_boundaries_require_quote_length_and_digest(changes):
    with pytest.raises(ValidationError):
        evidence(**changes)


def test_mitigation_fact_must_bind_to_the_exact_asset_snapshot():
    node = leaf("mitigation_confirmed", mitigation_key="fixture-mitigation")
    result = evaluate(
        node,
        supporting_facts=(fact(asset_snapshot_id="other-snapshot"),),
        rule_kind="observed_path",
    )
    assert result.value == "unknown"
    assert result.missing_requirements == ("leaf",)


def test_pending_fact_evidence_is_audited_without_becoming_a_confirmed_value():
    node = leaf("mitigation_confirmed", mitigation_key="fixture-mitigation")
    result = evaluate(
        node, supporting_facts=(fact(claim_origin="model_hypothesis"),), rule_kind="observed_path"
    )
    assert result.value == "unknown"
    assert result.evidence_ids == ("fixture-span",)
    assert result.limitations == ("unconfirmed_fact:fixture-claim",)
