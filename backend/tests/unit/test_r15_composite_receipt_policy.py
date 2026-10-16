"""Synthetic fixed snapshots through real R11 evaluation/binding; PG and live remain not_run."""

import hashlib
import json
from pathlib import Path

import pytest
from test_r15_recommendation_policy import (
    CUTOFF,
    fixture_event,
    fixture_receipt,
    fixture_selector,
    fixture_subscription,
)

from ai_intel.assessment.assessment_service import _bind_source_evidence, build_scope_watch
from ai_intel.assessment.conditions import condition_digest, parse_condition_tree
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assessment.rules import evaluate_rule
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import AssessmentStatus
from ai_intel.recommendations.policy import generate_recommendation_candidates

REVIEW_INPUTS = Path(__file__).resolve().parents[3] / (
    "reports/runs/recovery_r15_policy_fix1_20261016"
)


def evaluated_receipt(kind="all_of", configuration=True, *, nested=False):
    """Use evaluate_rule and the identical source binder called by AssessmentService.commit."""
    base = fixture_receipt()
    component = dict(
        node_id="component", kind="component_matches", ecosystem="PyPI", package_key="alpha"
    )
    configuration_leaf = dict(
        node_id="configuration",
        kind="configuration_equals",
        field="trust_remote_code",
        expected=True,
    )
    inner = dict(node_id="inner", kind=kind, children=[component, configuration_leaf])
    tree = parse_condition_tree(
        dict(node_id="outer", kind="all_of", children=[inner]) if nested else inner
    )
    rule = base.prepared.inputs.rule.model_copy(update={"condition_ast": tree})
    snapshot_payload = base.prepared.asset_snapshot.model_dump(mode="python")
    snapshot_payload.update(
        components=(
            dict(
                component_id="fixed-component",
                ecosystem="PyPI",
                package_name="alpha",
                display_name="Alpha",
                purl=None,
                version="1.0",
                version_scheme="pep440",
                image_digest=None,
                dependency_path=None,
                source_field_locator="/components/0",
            ),
        ),
        configuration=tuple(
            dict(
                name="trust_remote_code",
                value=value,
                source_field_locator=f"/configuration/{index}",
            )
            for index, value in enumerate(
                configuration if isinstance(configuration, tuple) else (configuration,)
            )
        ),
    )
    snapshot = type(base.prepared.asset_snapshot).model_validate(snapshot_payload)
    original = base.prepared.inputs.supports[0]
    supports = []
    for node_payload, quote in (
        (component, "Affected deployments include the Alpha package."),
        (configuration_leaf, "Affected deployments require trust_remote_code to be enabled."),
    ):
        node = parse_condition_tree(node_payload)
        evidence = original.evidence.model_copy(
            update={
                "evidence_id": f"fixed-{node.node_id}",
                "block_id": f"fixed-block-{node.node_id}",
                "quote_text": quote,
                "end_offset": len(quote),
                "quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
            }
        )
        supports.append(
            original.model_copy(
                update={
                    "binding": original.binding.model_copy(
                        update={
                            "node_id": node.node_id,
                            "claim_id": f"fixed-claim-{node.node_id}",
                            "evidence_id": evidence.evidence_id,
                        }
                    ),
                    "evidence": evidence,
                    "condition_sha256": condition_digest(node),
                }
            )
        )
    rule = rule.model_copy(
        update={
            "supporting_claim_ids": tuple(support.binding.claim_id for support in supports),
            "source_span_ids": tuple(support.evidence.evidence_id for support in supports),
        }
    )
    inputs = base.prepared.inputs.model_copy(update={"rule": rule, "supports": tuple(supports)})
    result = evaluate_rule(
        rule,
        snapshot,
        access_scope=AccessScope.for_authenticated_user(
            "fixture-user", "fixture-tenant", Role.ANALYST
        ),
    )
    result = result.model_copy(
        update={"evaluation_tree": _bind_source_evidence(result.evaluation_tree, inputs)}
    )
    prepared = base.prepared.model_copy(
        update={
            "inputs": inputs,
            "asset_snapshot": snapshot,
            "scope_watch": build_scope_watch(inputs, snapshot),
        }
    )
    return AssessmentReceipt.model_validate(
        {
            **base.model_dump(mode="python"),
            "prepared": prepared,
            "rule_result": result,
            "status": result.status,
            "missing_requirements": result.evaluation_tree.missing_requirements,
            "conflicts": result.evaluation_tree.observed_conflict_ids,
            "limitations": result.limitations,
        }
    )


def recommend_receipt(receipt):
    return generate_recommendation_candidates(
        fixture_subscription(asset_ids=(receipt.asset_id,)),
        (fixture_event(assessments=(receipt,)),),
        cutoff_at=CUTOFF,
    ).candidates[0]


@pytest.mark.parametrize(
    "name,status,kind",
    [
        ("supported", AssessmentStatus.SUPPORTED_APPLICABILITY, "supported_risk"),
        ("excluded", AssessmentStatus.EXCLUDED_WITH_EVIDENCE, "excluded_with_evidence"),
        ("unknown", AssessmentStatus.INSUFFICIENT_EVIDENCE, "prioritize_verification"),
    ],
)
def test_original_reviewer_receipt_bytes_are_reused_without_altering_status_or_hash(
    name, status, kind
):
    path = REVIEW_INPUTS / f"business_receipt_{name}.json"
    original = path.read_bytes()
    payload = json.loads(original)
    assert payload["data_mode"] == "fixture"
    assert payload["pg_authentication_and_commit"] == "not_run"
    receipt = AssessmentReceipt.model_validate(payload["receipt"])
    before = receipt.model_dump(mode="json")
    candidate = recommend_receipt(receipt)
    assert candidate.kind == kind and candidate.assessments[0].status == status
    assert {item.evidence_id for item in candidate.assessments[0].evidence} == {
        "review-component-evidence",
        "review-configuration-evidence",
    }
    assert candidate.assessments[0].input_digest == receipt.input_digest
    assert receipt.model_dump(mode="json") == before and path.read_bytes() == original


@pytest.mark.parametrize(
    "kind,configuration,nested,status",
    [
        ("all_of", True, False, AssessmentStatus.SUPPORTED_APPLICABILITY),
        ("all_of", False, False, AssessmentStatus.EXCLUDED_WITH_EVIDENCE),
        ("all_of", None, True, AssessmentStatus.INSUFFICIENT_EVIDENCE),
        ("all_of", (True, False), True, AssessmentStatus.CONFLICTING_EVIDENCE),
        ("any_of", None, True, AssessmentStatus.SUPPORTED_APPLICABILITY),
        ("any_of", (True, False), True, AssessmentStatus.SUPPORTED_APPLICABILITY),
    ],
)
def test_business_tree_supported_excluded_unknown_conflict_and_nondecisive_conflicts(
    kind,
    configuration,
    nested,
    status,
):
    receipt = evaluated_receipt(kind, configuration, nested=nested)
    assert receipt.status == status
    assert receipt.rule_result.evaluation_tree.evidence_ids == ()
    candidate = recommend_receipt(receipt)
    reference = candidate.assessments[0]
    assert reference.status == status
    assert reference.evidence == tuple(
        sorted(
            (support.evidence for support in receipt.prepared.inputs.supports),
            key=lambda item: item.evidence_id,
        )
    )
    assert reference.conflicts == receipt.conflicts
    assert reference.missing_requirements == receipt.missing_requirements
    if isinstance(configuration, tuple):
        assert reference.conflicts


def test_duplicate_tree_and_checked_support_reference_retains_one_unchanged_object():
    receipt = evaluated_receipt(configuration=None, nested=True)
    inputs = receipt.prepared.inputs
    repeated = receipt.model_copy(
        update={
            "prepared": receipt.prepared.model_copy(
                update={
                    "inputs": inputs.model_copy(
                        update={"supports": (*inputs.supports, inputs.supports[0])}
                    )
                }
            )
        }
    )
    reference = recommend_receipt(repeated).assessments[0]
    assert len(reference.evidence) == 2
    assert reference.evidence[0] == inputs.supports[0].evidence


def test_same_evidence_identity_with_conflicting_quote_is_rejected():
    receipt = evaluated_receipt(configuration=None)
    inputs = receipt.prepared.inputs
    support = inputs.supports[0]
    quote = "A different immutable source passage."
    changed = support.model_copy(
        update={
            "evidence": support.evidence.model_copy(
                update={
                    "quote_text": quote,
                    "end_offset": len(quote),
                    "quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
                }
            )
        }
    )
    receipt = receipt.model_copy(
        update={
            "prepared": receipt.prepared.model_copy(
                update={
                    "inputs": inputs.model_copy(update={"supports": (*inputs.supports, changed)})
                }
            )
        }
    )
    with pytest.raises(ValueError, match=r"^assessment_evidence_identity_mismatch$"):
        recommend_receipt(receipt)


@pytest.mark.parametrize("change", ["wrong_node", "wrong_id", "unverified", "pending", "context"])
def test_child_support_must_retain_its_validated_node_and_evidence_binding(change):
    receipt = evaluated_receipt(configuration=None)
    inputs = receipt.prepared.inputs
    support = inputs.supports[0]
    changed = {
        "wrong_node": support.model_copy(
            update={"binding": support.binding.model_copy(update={"node_id": "not-in-tree"})}
        ),
        "wrong_id": support.model_copy(
            update={
                "binding": support.binding.model_copy(update={"evidence_id": "not-the-bound-span"})
            }
        ),
        "unverified": support.model_copy(
            update={
                "evidence": support.evidence.model_copy(update={"validation_status": "unverified"})
            }
        ),
        "pending": support.model_copy(update={"semantic_status": "pending"}),
        "context": support.model_copy(
            update={"evidence": support.evidence.model_copy(update={"support_kind": "context"})}
        ),
    }[change]
    receipt = receipt.model_copy(
        update={
            "prepared": receipt.prepared.model_copy(
                update={
                    "inputs": inputs.model_copy(update={"supports": (changed, inputs.supports[1])})
                }
            )
        }
    )
    with pytest.raises(ValueError, match=r"^assessment_evidence_binding_mismatch$"):
        recommend_receipt(receipt)


def test_refuting_child_evidence_is_retained_instead_of_becoming_missing():
    receipt = evaluated_receipt(configuration=None)
    inputs = receipt.prepared.inputs
    first, second = inputs.supports
    refuting = second.model_copy(
        update={
            "semantic_status": "refutes",
            "evidence": second.evidence.model_copy(update={"support_kind": "refutes"}),
        }
    )
    receipt = receipt.model_copy(
        update={
            "prepared": receipt.prepared.model_copy(
                update={"inputs": inputs.model_copy(update={"supports": (first, refuting)})}
            )
        }
    )
    candidate = recommend_receipt(receipt)
    assert candidate.kind == "prioritize_verification"
    assert candidate.assessments[0].evidence[1].support_kind == "refutes"
    assert candidate.assessments[0].status == AssessmentStatus.INSUFFICIENT_EVIDENCE


def test_selector_fixtures_keep_independent_revision_span_and_consistent_payloads():
    selectors = (
        fixture_selector(),
        fixture_selector(value="PyPI:beta"),
        fixture_selector("risk_topic", "prompt_injection"),
        fixture_selector("consequence", "high"),
        fixture_selector(),
    )
    by_identity = {}
    revisions = set()
    for selector in selectors:
        for citation in selector.citations:
            previous = by_identity.setdefault(citation.evidence_id, citation)
            assert previous == citation
            assert citation.locator == f"text[0:{len(citation.quote)}]"
            revisions.add(citation.revision_id)
    assert len(by_identity) == len(revisions) == 4


def test_conflicting_immutable_selector_payloads_across_events_are_rejected():
    alpha = fixture_selector()
    beta = fixture_selector(value="PyPI:beta")
    beta = beta.model_copy(
        update={
            "citations": (
                beta.citations[0].model_copy(
                    update={"evidence_id": alpha.citations[0].evidence_id}
                ),
            )
        }
    )
    with pytest.raises(ValueError, match=r"^selector_evidence_identity_mismatch$"):
        generate_recommendation_candidates(
            fixture_subscription(),
            (
                fixture_event(selectors=(alpha,)),
                fixture_event(event_id="beta", selectors=(beta,)),
            ),
            cutoff_at=CUTOFF,
        )
