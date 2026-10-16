"""Explicit synthetic R15 policy fixtures; no PostgreSQL authorization is simulated."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest
from pydantic import ValidationError

from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.assessment.conditions import parse_condition_tree
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assessment.rules import ConditionRule, RuleValidationResult
from ai_intel.domain.enums import AssessmentStatus, ClaimStatus, FreshnessStatus
from ai_intel.recommendations.contracts import (
    MAX_CANDIDATES,
    MAX_INPUT_EVENTS,
    RecommendationEventInput,
    RecommendationSubscription,
    SelectorEvidence,
)
from ai_intel.recommendations.policy import generate_recommendation_candidates
from ai_intel.recommendations.report_builder import build_report_candidate

CUTOFF = datetime(2026, 10, 16, 0, tzinfo=UTC)


def fixture_subscription(**updates):
    payload = dict(
        subscription_id="fixture-subscription",
        tenant_id="fixture-tenant",
        user_id="fixture-user",
        enabled=True,
        product_keys=("PyPI:alpha",),
    )
    payload.update(updates)
    return RecommendationSubscription.model_validate(payload)


def fixture_selector(kind="product", value="PyPI:alpha", **updates):
    quote = {
        "product": f"Product {value} is affected under the stated conditions.",
        "risk_topic": f"The described risk mechanism is {value}.",
        "consequence": f"The stated consequence category is {value}.",
    }[kind]
    revision_id = uuid5(NAMESPACE_URL, f"fixture-selector-revision:{kind}:{value}")
    payload = dict(
        selector_kind=kind,
        selector_value=value,
        claim_id="fixture-claim",
        claim_status="supported",
        claim_origin="source_explicit",
        support_kind="supports",
        validation_status="validated",
        citations=(
            CitationProjection(
                evidence_id=uuid5(NAMESPACE_URL, f"fixture-selector-evidence:{kind}:{value}"),
                revision_id=revision_id,
                quote=quote,
                locator=f"text[0:{len(quote)}]",
                source_uri=f"https://fixture.example/advisory/{revision_id}",
            ),
        ),
    )
    payload.update(updates)
    return SelectorEvidence.model_validate(payload)


def fixture_event(**updates):
    payload = dict(
        event_id="fixture-event",
        material_version="fixture-material-1",
        observed_at=CUTOFF - timedelta(hours=1),
        valid_from=CUTOFF - timedelta(days=30),
        status_at_cutoff="supported",
        freshness_at_cutoff="current",
        current_status="supported",
        current_freshness="current",
        current_state_checked_at=CUTOFF,
        selectors=(fixture_selector(),),
    )
    payload.update(updates)
    return RecommendationEventInput.model_validate(payload)


def fixture_receipt(status=AssessmentStatus.INSUFFICIENT_EVIDENCE, **updates):
    event_id = updates.get("event_id", "fixture-event")
    quote = {
        AssessmentStatus.SUPPORTED_APPLICABILITY: "Alpha version 1 is affected.",
        AssessmentStatus.EXCLUDED_WITH_EVIDENCE: (
            "Alpha version 1 is excluded from the affected scope."
        ),
        AssessmentStatus.INSUFFICIENT_EVIDENCE: (
            "Affected deployments require a missing configuration condition."
        ),
        AssessmentStatus.CONFLICTING_EVIDENCE: "Sources disagree on the affected scope of Alpha.",
    }[status]
    evidence = dict(
        evidence_id="fixture-evidence",
        source_id="fixture-source",
        document_id="fixture-doc",
        revision_id="fixture-revision",
        block_id="fixture-block",
        start_offset=0,
        end_offset=len(quote),
        quote_text=quote,
        quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
        scope=dict(visibility="public", tenant_id=None),
        support_kind="supports",
        validation_status="validated",
    )
    rule = ConditionRule(
        rule_id="fixture-rule",
        version=1,
        event_id=event_id,
        rule_kind="software_applicability",
        condition_ast=parse_condition_tree(
            dict(
                node_id="component",
                kind="component_matches",
                ecosystem="PyPI",
                package_key="alpha",
            )
        ),
        supporting_claim_ids=("fixture-claim",),
        source_span_ids=("fixture-evidence",),
        scope=dict(visibility="public", tenant_id=None),
        status="published",
        published_at=CUTOFF - timedelta(days=1),
    )
    validation = RuleValidationResult(
        rule_id=rule.rule_id,
        rule_version=1,
        schema_version="r11-condition-1",
        policy_version="fixture-policy",
        condition_sha256="a" * 64,
        eligible=True,
        automatic_publication_eligible=False,
        resulting_status="published",
        missing_requirements=(),
        conflicts=(),
        pending_review=(),
        supporting_claim_ids=rule.supporting_claim_ids,
        source_span_ids=rule.source_span_ids,
        source_revision_ids=("fixture-revision",),
        source_supports=(),
        scope=rule.scope,
    )
    missing = (
        ("configuration.authentication_required",)
        if status == (AssessmentStatus.INSUFFICIENT_EVIDENCE)
        else ()
    )
    conflicts = ("fixture-conflict",) if status == AssessmentStatus.CONFLICTING_EVIDENCE else ()
    tree_value = {
        AssessmentStatus.SUPPORTED_APPLICABILITY: "true",
        AssessmentStatus.EXCLUDED_WITH_EVIDENCE: "false",
        AssessmentStatus.CONFLICTING_EVIDENCE: "conflict",
        AssessmentStatus.INSUFFICIENT_EVIDENCE: "unknown",
    }[status]
    payload = dict(
        assessment_id="fixture-assessment",
        tenant_id="fixture-tenant",
        asset_id="fixture-asset",
        asset_snapshot_id="fixture-snapshot",
        event_id="fixture-event",
        rule_id="fixture-rule",
        rule_version=1,
        knowledge_epoch=4,
        scope_epoch_map={"public": 4},
        status=status,
        freshness="current",
        missing_requirements=missing,
        conflicts=conflicts,
        limitations=("fixture_scope",),
        exposure_result="not_evaluated",
        input_digest="d" * 64,
        created_at=CUTOFF - timedelta(minutes=30),
        rule_result=dict(
            rule_id="fixture-rule",
            rule_version=1,
            rule_kind="software_applicability",
            asset_snapshot_id="fixture-snapshot",
            condition_sha256="a" * 64,
            status=status,
            limitations=("fixture_scope",),
            evaluation_tree=dict(
                node_id="component",
                value=tree_value,
                reason_code="fixture-condition-result",
                evidence_ids=("fixture-evidence",),
                missing_requirements=missing,
                observed_conflict_ids=conflicts,
            ),
        ),
        prepared=dict(
            preparation_receipt_id="fixture-preparation",
            actor_user_id="fixture-user",
            actor_role="analyst",
            permission_version=1,
            asset_active=True,
            asset_current_snapshot_id="fixture-snapshot",
            asset_fingerprint="f" * 64,
            input_digest="d" * 64,
            asset_snapshot=dict(
                schema_version="r11-asset-candidate-1",
                snapshot_id="fixture-snapshot",
                asset_id="fixture-asset",
                tenant_id="fixture-tenant",
                snapshot_number=1,
                observed_at=CUTOFF - timedelta(days=1),
                recorded_at=CUTOFF - timedelta(days=1),
                source_kind="fixture",
                inventory_completeness="unknown",
                declared_scope=(),
                components=(),
                configuration=(),
                tool_permissions=None,
                input_channels=None,
                network_exposure=None,
                snapshot_sha256="b" * 64,
            ),
            inputs=dict(
                rule=rule,
                author_user_id="fixture-author",
                event_version=1,
                event_status="active",
                sources=(),
                active_revision_ids=("fixture-revision",),
                scope_epoch_map={"public": 4},
                validation=validation,
                input_digest="c" * 64,
                supports=(
                    dict(
                        binding=dict(
                            node_id="component",
                            claim_id="fixture-claim",
                            evidence_id="fixture-evidence",
                        ),
                        condition_sha256="a" * 64,
                        claim_fingerprint="a" * 64,
                        source_fingerprint="a" * 64,
                        review_fingerprint="a" * 64,
                        input_digest="a" * 64,
                        evidence=evidence,
                        semantic_status="supports",
                        range_completeness_confirmed=False,
                    ),
                ),
            ),
            scope_watch=dict(
                tenant_id="fixture-tenant",
                event_ids=(event_id,),
                package_keys=("PyPI:alpha",),
                rule_id="fixture-rule",
                rule_version=1,
                rule_kind="software_applicability",
                scope_epoch_map={"public": 4},
                selected_rule_ids=("fixture-rule",),
                no_published_rule=False,
            ),
        ),
    )
    payload.update(updates)
    return AssessmentReceipt.model_validate(payload)


def test_t39_c01_two_users_have_distinct_evidence_supported_interests():
    events = (
        fixture_event(),
        fixture_event(event_id="fixture-beta", selectors=(fixture_selector(value="PyPI:beta"),)),
    )
    alpha = generate_recommendation_candidates(fixture_subscription(), events, cutoff_at=CUTOFF)
    beta = generate_recommendation_candidates(
        fixture_subscription(
            subscription_id="fixture-beta-sub",
            user_id="fixture-beta-user",
            product_keys=("PyPI:beta",),
        ),
        events,
        cutoff_at=CUTOFF,
    )
    assert [item.key.event_id for item in alpha.candidates] == ["fixture-event"]
    assert [item.key.event_id for item in beta.candidates] == ["fixture-beta"]
    assert alpha.candidates[0].reasons[0].matched_key == "PyPI:alpha"
    assert beta.candidates[0].reasons[0].citations[0].revision_id == (
        events[1].selectors[0].citations[0].revision_id
    )
    assert "PyPI:beta" in beta.candidates[0].reasons[0].citations[0].quote
    assert "PyPI:alpha" in alpha.candidates[0].reasons[0].citations[0].quote
    assert alpha.candidates[0].kind == "intelligence_update"


def test_t39_c02_repeated_poll_and_persisted_key_do_not_repeat_material_version():
    subscription = fixture_subscription()
    first = generate_recommendation_candidates(
        subscription, (fixture_event(),) * 2, cutoff_at=CUTOFF
    )
    assert len(first.candidates) == 1
    replay = generate_recommendation_candidates(
        subscription, (fixture_event(),), cutoff_at=CUTOFF, existing_keys=(first.candidates[0].key,)
    )
    assert replay.candidates == ()
    revised = generate_recommendation_candidates(
        subscription,
        (fixture_event(material_version="fixture-material-2"),),
        cutoff_at=CUTOFF,
        existing_keys=(first.candidates[0].key,),
    )
    assert revised.candidates[0].key.material_version == "fixture-material-2"


def test_material_version_collision_is_rejected_instead_of_order_dependent_winner():
    with pytest.raises(ValueError, match="material_version_collision"):
        generate_recommendation_candidates(
            fixture_subscription(),
            (
                fixture_event(),
                fixture_event(selectors=(fixture_selector(value="PyPI:beta"),)),
            ),
            cutoff_at=CUTOFF,
        )


def test_two_active_material_versions_for_one_event_are_rejected():
    with pytest.raises(ValueError, match="ambiguous_active_material_versions"):
        generate_recommendation_candidates(
            fixture_subscription(),
            (fixture_event(), fixture_event(material_version="fixture-material-2")),
            cutoff_at=CUTOFF,
        )


def test_only_latest_as_of_material_version_is_used_when_old_validity_has_ended():
    batch = generate_recommendation_candidates(
        fixture_subscription(),
        (fixture_event(valid_until=CUTOFF), fixture_event(material_version="fixture-material-2")),
        cutoff_at=CUTOFF,
    )
    assert [item.key.material_version for item in batch.candidates] == ["fixture-material-2"]


def test_t39_c03_exclusion_retains_original_receipt_and_does_not_claim_supported_risk():
    event = fixture_event(assessments=(fixture_receipt(AssessmentStatus.EXCLUDED_WITH_EVIDENCE),))
    batch = generate_recommendation_candidates(
        fixture_subscription(asset_ids=("fixture-asset",)), (event,), cutoff_at=CUTOFF
    )
    candidate = batch.candidates[0]
    assert candidate.kind == "excluded_with_evidence"
    assert candidate.assessments[0].status == AssessmentStatus.EXCLUDED_WITH_EVIDENCE
    assert candidate.assessments[0].evidence[0].quote_text == (
        "Alpha version 1 is excluded from the affected scope."
    )
    assert candidate.assessments[0].rule_version == 1


@pytest.mark.parametrize(
    "status", [AssessmentStatus.INSUFFICIENT_EVIDENCE, AssessmentStatus.CONFLICTING_EVIDENCE]
)
def test_t39_c04_high_consequence_unknown_or_conflict_is_priority_verification(status):
    event = fixture_event(
        selectors=(fixture_selector(), fixture_selector("consequence", "high")),
        assessments=(fixture_receipt(status),),
    )
    batch = generate_recommendation_candidates(
        fixture_subscription(asset_ids=("fixture-asset",)), (event,), cutoff_at=CUTOFF
    )
    item = batch.candidates[0]
    assert (item.kind, item.priority_bucket) == ("prioritize_verification", 0)
    assert item.assessments[0].status == status
    assert item.assessments[0].asset_snapshot_id == "fixture-snapshot"
    assert "unresolved_evidence_requires_verification" in item.limitations
    report = build_report_candidate(batch, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF)
    assert report.verification_items == (item,) and report.supported_risks == ()


def test_supported_risk_has_receipt_evidence_and_separate_report_section():
    batch = generate_recommendation_candidates(
        fixture_subscription(asset_ids=("fixture-asset",)),
        (fixture_event(assessments=(fixture_receipt(AssessmentStatus.SUPPORTED_APPLICABILITY),)),),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates[0].kind == "supported_risk"
    assert batch.candidates[0].assessments[0].knowledge_epoch == 4
    report = build_report_candidate(batch, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF)
    assert len(report.supported_risks) == 1 and report.verification_items == ()


def test_asset_interest_uses_existing_unknown_receipt_without_needing_product_selector():
    subscription = fixture_subscription(product_keys=(), asset_ids=("fixture-asset",))
    batch = generate_recommendation_candidates(
        subscription,
        (fixture_event(selectors=(), assessments=(fixture_receipt(),)),),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates[0].kind == "prioritize_verification"
    assert batch.candidates[0].reasons[0].assessment_id == "fixture-assessment"


def test_unknown_unsupported_rule_receipt_preserves_missing_requirements():
    batch = generate_recommendation_candidates(
        fixture_subscription(product_keys=(), asset_ids=("fixture-asset",)),
        (
            fixture_event(
                selectors=(),
                assessments=(
                    fixture_receipt(rule_result=None, missing_requirements=("unsupported_rule",)),
                ),
            ),
        ),
        cutoff_at=CUTOFF,
    )
    reference = batch.candidates[0].assessments[0]
    assert reference.status == AssessmentStatus.INSUFFICIENT_EVIDENCE
    assert reference.missing_requirements == ("unsupported_rule",) and reference.evidence == ()


def test_high_consequence_unknown_precedes_high_consequence_supported_risk():
    selectors = (fixture_selector(), fixture_selector("consequence", "high"))
    batch = generate_recommendation_candidates(
        fixture_subscription(asset_ids=("fixture-asset",), maximum_priority_bucket=0),
        (
            fixture_event(selectors=selectors, assessments=(fixture_receipt(),)),
            fixture_event(
                event_id="supported-event",
                selectors=selectors,
                assessments=(
                    fixture_receipt(
                        AssessmentStatus.SUPPORTED_APPLICABILITY, event_id="supported-event"
                    ),
                ),
            ),
        ),
        cutoff_at=CUTOFF,
    )
    assert [item.kind for item in batch.candidates] == ["prioritize_verification", "supported_risk"]
    assert [item.priority_bucket for item in batch.candidates] == [0, 0]


def test_unverified_high_consequence_claim_does_not_invent_urgency():
    batch = generate_recommendation_candidates(
        fixture_subscription(asset_ids=("fixture-asset",)),
        (
            fixture_event(
                selectors=(
                    fixture_selector(),
                    fixture_selector("consequence", "high", claim_status="unverified"),
                ),
                assessments=(fixture_receipt(),),
            ),
        ),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates[0].kind == "prioritize_verification"
    assert batch.candidates[0].priority_bucket == 2
    assert all(reason.code != "high_consequence" for reason in batch.candidates[0].reasons)


def test_event_conflict_is_verification_even_when_product_relation_is_supported():
    batch = generate_recommendation_candidates(
        fixture_subscription(),
        (fixture_event(status_at_cutoff="disputed", current_status="disputed"),),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates[0].kind == "prioritize_verification"


def test_t39_c05_disabled_subscription_has_explicit_stop_and_does_not_mutate_other_user():
    enabled = fixture_subscription()
    disabled = fixture_subscription(enabled=False)
    stopped = generate_recommendation_candidates(disabled, (fixture_event(),), cutoff_at=CUTOFF)
    assert stopped.stop_reason == "disabled" and stopped.candidates == ()
    report = build_report_candidate(stopped, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF)
    assert report.stop_reason == "disabled" and not report.partial
    assert generate_recommendation_candidates(
        enabled, (fixture_event(),), cutoff_at=CUTOFF
    ).candidates


def test_t39_c06_mismatched_tenant_receipt_is_rejected_as_input_consistency_only():
    with pytest.raises(ValueError, match="assessment_scope_mismatch"):
        generate_recommendation_candidates(
            fixture_subscription(),
            (fixture_event(assessments=(fixture_receipt(tenant_id="other-tenant"),)),),
            cutoff_at=CUTOFF,
        )


@pytest.mark.parametrize(
    "updates",
    [
        dict(claim_status="unverified"),
        dict(claim_status="disputed"),
        dict(support_kind="context"),
        dict(support_kind="refutes"),
        dict(validation_status="unverified"),
        dict(claim_origin="model_hypothesis"),
    ],
)
def test_citation_existence_does_not_prove_selector_match(updates):
    batch = generate_recommendation_candidates(
        fixture_subscription(),
        (fixture_event(selectors=(fixture_selector(**updates),)),),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates == () and batch.stop_reason == "no_supported_subscription_match"


def test_explicit_risk_topic_subscription_matches_verified_topic_only():
    subscription = fixture_subscription(product_keys=(), risk_topics=("prompt_injection",))
    batch = generate_recommendation_candidates(
        subscription,
        (fixture_event(selectors=(fixture_selector("risk_topic", "prompt_injection"),)),),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates[0].reasons[0].code == "risk_topic_match"


@pytest.mark.parametrize(
    "updates",
    [
        dict(status_at_cutoff="withdrawn", current_status="withdrawn"),
        dict(status_at_cutoff="superseded", current_status="superseded"),
        dict(freshness_at_cutoff="stale", current_freshness="stale"),
        dict(freshness_at_cutoff="unknown", current_freshness="unknown"),
        dict(valid_until=CUTOFF),
        dict(
            observed_at=CUTOFF + timedelta(seconds=1),
            current_state_checked_at=CUTOFF + timedelta(seconds=1),
        ),
    ],
)
def test_invalid_at_cutoff_events_are_not_new_recommendations(updates):
    assert (
        generate_recommendation_candidates(
            fixture_subscription(), (fixture_event(**updates),), cutoff_at=CUTOFF
        ).candidates
        == ()
    )


def test_stale_assessment_does_not_turn_product_news_into_supported_risk():
    batch = generate_recommendation_candidates(
        fixture_subscription(asset_ids=("fixture-asset",)),
        (
            fixture_event(
                assessments=(
                    fixture_receipt(AssessmentStatus.SUPPORTED_APPLICABILITY, freshness="stale"),
                )
            ),
        ),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates[0].kind == "intelligence_update"
    assert batch.candidates[0].assessments == ()


def test_missing_assessment_cannot_prove_asset_match_or_negation():
    batch = generate_recommendation_candidates(
        fixture_subscription(product_keys=(), asset_ids=("fixture-asset",)),
        (fixture_event(),),
        cutoff_at=CUTOFF,
    )
    assert batch.candidates == ()


def test_receipt_mismatched_snapshot_or_missing_support_is_rejected():
    for receipt in (
        fixture_receipt(asset_snapshot_id="other-snapshot"),
        fixture_receipt().model_copy(
            update={
                "prepared": fixture_receipt().prepared.model_copy(
                    update={
                        "inputs": fixture_receipt().prepared.inputs.model_copy(
                            update={"supports": ()}
                        )
                    }
                )
            }
        ),
    ):
        with pytest.raises(ValueError, match=r"assessment_.*binding_mismatch"):
            generate_recommendation_candidates(
                fixture_subscription(asset_ids=("fixture-asset",)),
                (fixture_event(assessments=(receipt,)),),
                cutoff_at=CUTOFF,
            )


def test_candidate_order_is_deterministic_under_permuted_event_input():
    events = (fixture_event(event_id="z"), fixture_event(event_id="a"))
    forward = generate_recommendation_candidates(fixture_subscription(), events, cutoff_at=CUTOFF)
    reverse = generate_recommendation_candidates(
        fixture_subscription(), events[::-1], cutoff_at=CUTOFF
    )
    assert forward == reverse
    assert [item.key.event_id for item in forward.candidates] == ["a", "z"]


def test_item_budget_has_explicit_unselected_keys_for_continuation():
    batch = generate_recommendation_candidates(
        fixture_subscription(),
        (
            fixture_event(event_id="a"),
            fixture_event(event_id="b"),
            fixture_event(event_id="c"),
        ),
        cutoff_at=CUTOFF,
        max_candidates=2,
    )
    assert batch.partial and batch.stop_reason == "item_budget" and batch.eligible_count == 3
    assert [key.event_id for key in batch.continuation_keys] == ["c"]
    report = build_report_candidate(
        batch, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF, max_items=1
    )
    assert report.partial and report.stop_reason == "item_budget"
    assert [key.event_id for key in report.continuation_keys] == ["b", "c"]


@pytest.mark.parametrize("budget", [True, False, 0, -1, MAX_CANDIDATES + 1, 1.5])
def test_candidate_and_report_budget_reject_boolean_negative_or_excess(budget):
    with pytest.raises(ValueError, match="item_budget_out_of_bounds"):
        generate_recommendation_candidates(
            fixture_subscription(), (), cutoff_at=CUTOFF, max_candidates=budget
        )
    batch = generate_recommendation_candidates(fixture_subscription(), (), cutoff_at=CUTOFF)
    with pytest.raises(ValueError, match="item_budget_out_of_bounds"):
        build_report_candidate(
            batch, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF, max_items=budget
        )


def test_input_event_budget_is_bounded_even_for_duplicates():
    with pytest.raises(ValueError, match="input_event_budget_exceeded"):
        generate_recommendation_candidates(
            fixture_subscription(), (fixture_event(),) * (MAX_INPUT_EVENTS + 1), cutoff_at=CUTOFF
        )


def test_daily_weekly_left_open_window_and_late_source_observation():
    events = (
        fixture_event(event_id="late-source", source_changed_at=CUTOFF - timedelta(days=60)),
        fixture_event(event_id="daily-boundary", observed_at=CUTOFF - timedelta(days=1)),
        fixture_event(event_id="weekly-boundary", observed_at=CUTOFF - timedelta(days=7)),
        fixture_event(event_id="right-boundary", observed_at=CUTOFF),
    )
    batch = generate_recommendation_candidates(fixture_subscription(), events, cutoff_at=CUTOFF)
    day = build_report_candidate(batch, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF)
    week = build_report_candidate(batch, frequency="week", cutoff_at=CUTOFF, generated_at=CUTOFF)
    assert {item.key.event_id for item in day.intelligence_updates} == {
        "late-source",
        "right-boundary",
    }
    assert {item.key.event_id for item in week.intelligence_updates} == {
        "late-source",
        "right-boundary",
        "daily-boundary",
    }
    assert day.window_basis == "first_material_observed_at"
    assert next(
        item for item in day.intelligence_updates if item.key.event_id == "late-source"
    ).source_changed_at == CUTOFF - timedelta(days=60)


def test_historical_report_keeps_then_valid_evidence_and_separate_current_withdrawal():
    generated = CUTOFF + timedelta(days=2)
    batch = generate_recommendation_candidates(
        fixture_subscription(),
        (
            fixture_event(
                current_status="withdrawn",
                current_freshness="stale",
                current_state_checked_at=generated,
                valid_until=CUTOFF + timedelta(days=1),
            ),
        ),
        cutoff_at=CUTOFF,
    )
    historical = build_report_candidate(
        batch, frequency="day", cutoff_at=CUTOFF, generated_at=generated
    )
    assert historical.temporal_mode == "as_of_cutoff"
    item = historical.intelligence_updates[0]
    assert item.freshness_at_cutoff == FreshnessStatus.CURRENT
    assert item.current_status == ClaimStatus.WITHDRAWN
    assert item.current_state_checked_at == generated
    assert item.validity_as_of == CUTOFF
    current = generate_recommendation_candidates(
        fixture_subscription(),
        (
            fixture_event(
                current_status="withdrawn",
                status_at_cutoff="withdrawn",
                current_state_checked_at=generated,
            ),
        ),
        cutoff_at=generated,
    )
    assert current.candidates == ()
    assert historical.intelligence_updates[0] == item


def test_naive_cutoff_and_inconsistent_current_snapshot_are_rejected():
    with pytest.raises(ValidationError):
        generate_recommendation_candidates(
            fixture_subscription(), (), cutoff_at=datetime(2026, 10, 16)
        )
    with pytest.raises(ValueError, match="as_of_state_conflicts_with_current_state"):
        generate_recommendation_candidates(
            fixture_subscription(), (fixture_event(current_status="withdrawn"),), cutoff_at=CUTOFF
        )


def test_report_refuses_other_cutoff_future_generation_and_other_user_candidates():
    batch = generate_recommendation_candidates(
        fixture_subscription(), (fixture_event(),), cutoff_at=CUTOFF
    )
    for cutoff, generated in (
        (CUTOFF + timedelta(days=1), CUTOFF + timedelta(days=1)),
        (CUTOFF, CUTOFF - timedelta(seconds=1)),
    ):
        with pytest.raises(ValueError, match="report_cutoff_mismatch"):
            build_report_candidate(batch, frequency="day", cutoff_at=cutoff, generated_at=generated)
    polluted = batch.model_copy(
        update={"candidates": (batch.candidates[0].model_copy(update={"user_id": "other-user"}),)}
    )
    with pytest.raises(ValueError, match="report_candidate_scope_mismatch"):
        build_report_candidate(polluted, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF)
