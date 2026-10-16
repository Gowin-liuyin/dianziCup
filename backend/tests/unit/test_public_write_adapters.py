"""Explicit fixture-only service doubles test public projection and current-authority boundaries."""

import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tests.r11_assessment_http_fixtures import synthetic_receipt

from ai_intel.answering.service import GroundedQuestionService, QuestionFailure
from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.api.public_write_adapters import (
    PublicWriteMappingError,
    ask_current_question,
    parse_public_ask_request,
    parse_public_stack_request,
    stack_current_assessments,
)
from ai_intel.api.question_contracts import QuestionAnswerResponse
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.conditions import (
    ConditionEvaluation,
    EvidenceReference,
    condition_digest,
    parse_condition_tree,
)
from ai_intel.assessment.persistence_contracts import CheckedSupport
from ai_intel.assessment.rules import RuleEvaluation
from ai_intel.assets.inventory_contracts import ComponentResponse
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.enums import AssessmentStatus, FreshnessStatus

FIXTURE_SCOPE = AccessScope.for_authenticated_user("unit-owner", "fixture-tenant", Role.ANALYST)
STAMP = datetime(2026, 10, 16, tzinfo=UTC)
EVIDENCE_ID = str(UUID(int=7))
REVISION_ID = str(UUID(int=8))


def fixture_request(**updates):
    component = dict(ecosystem="PyPI", package_name="fixture", version="1.0")
    component.update(updates)
    return parse_public_stack_request(json.dumps(dict(components=[component])).encode())


def fixture_receipt(status=AssessmentStatus.INSUFFICIENT_EVIDENCE, *, freshness="current"):
    receipt = synthetic_receipt()
    component = ComponentResponse(
        component_id=str(UUID(int=3)),
        ecosystem="PyPI",
        package_name="fixture",
        display_name=None,
        purl="pkg:pypi/fixture@1.0",
        version="1.0",
        version_scheme="pep440",
        image_digest=None,
        dependency_path=None,
        source_field_locator="/components/0",
    )
    snapshot = receipt.prepared.asset_snapshot.model_copy(update={"components": (component,)})
    reference = EvidenceReference(
        evidence_id=EVIDENCE_ID,
        source_id=str(UUID(int=9)),
        document_id=str(UUID(int=10)),
        revision_id=REVISION_ID,
        block_id=str(UUID(int=11)),
        start_offset=0,
        end_offset=5,
        quote_text="quote",
        quote_sha256=hashlib.sha256(b"quote").hexdigest(),
        scope=dict(visibility="public"),
        support_kind="supports",
        validation_status="validated",
    )
    support = CheckedSupport(
        binding=dict(node_id="leaf", claim_id=str(UUID(int=12)), evidence_id=EVIDENCE_ID),
        condition_sha256="a" * 64,
        claim_fingerprint="b" * 64,
        source_fingerprint="c" * 64,
        review_fingerprint="d" * 64,
        input_digest="e" * 64,
        evidence=reference,
        semantic_status="supports",
        range_completeness_confirmed=True,
    )
    inputs = receipt.prepared.inputs.model_copy(
        update={
            "supports": (support,),
            "rule": receipt.prepared.inputs.rule.model_copy(
                update={
                    "condition_ast": parse_condition_tree(
                        {
                            "node_id": "leaf",
                            "kind": "component_matches",
                            "ecosystem": "PyPI",
                            "package_key": "fixture",
                        }
                    )
                }
            ),
        }
    )
    prepared = receipt.prepared.model_copy(update={"asset_snapshot": snapshot, "inputs": inputs})
    value = {
        AssessmentStatus.SUPPORTED_APPLICABILITY: "true",
        AssessmentStatus.EXCLUDED_WITH_EVIDENCE: "false",
        AssessmentStatus.INSUFFICIENT_EVIDENCE: "unknown",
        AssessmentStatus.CONFLICTING_EVIDENCE: "conflict",
    }[status]
    rule_result = RuleEvaluation(
        rule_id=receipt.rule_id,
        rule_version=1,
        rule_kind="software_applicability",
        asset_snapshot_id=receipt.asset_snapshot_id,
        condition_sha256=condition_digest(inputs.rule.condition_ast),
        evaluation_tree=ConditionEvaluation(
            node_id="leaf", value=value, reason_code="source_checked", evidence_ids=(EVIDENCE_ID,)
        ),
        status=status,
        limitations=("synthetic-unit-fixture",),
    )
    return receipt.model_copy(
        update={
            "prepared": prepared,
            "status": status,
            "freshness": FreshnessStatus(freshness),
            "rule_result": rule_result,
        }
    )


def fixture_services(receipt):
    assessment = Mock(spec=AssessmentService)
    assessment.read_in_session.return_value = receipt
    knowledge = KnowledgeReadService(Mock(spec=Session), FIXTURE_SCOPE, "fixture")
    knowledge.session.scalar.return_value = "/source/paragraph/0"
    projection = EvidenceResponse(
        span_id=UUID(EVIDENCE_ID),
        revision_id=UUID(REVISION_ID),
        block_id=UUID(int=11),
        start_offset=0,
        end_offset=5,
        quote_text="quote",
        quote_sha256=hashlib.sha256(b"quote").hexdigest(),
        locator_kind="text",
        page_number=None,
        json_pointer=None,
        verified_at=STAMP,
        source_uri="https://example.test/fixture",
        source_published_at=None,
        source_modified_at=None,
        first_observed_at=STAMP,
        ingested_at=STAMP,
        data_mode="fixture",
    )
    knowledge.read_evidence = Mock(return_value=projection)
    return assessment, knowledge


@pytest.mark.parametrize("status", list(AssessmentStatus))
def test_current_shared_receipt_preserves_all_four_states_and_full_citation(status):
    receipt = fixture_receipt(status)
    assessment, knowledge = fixture_services(receipt)
    result = stack_current_assessments(
        fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
    )
    item = result.results[0]
    assert item.status == status and item.freshness == FreshnessStatus.CURRENT
    assert item.citations[0].evidence_id == UUID(EVIDENCE_ID)
    assert item.citations[0].revision_id == UUID(REVISION_ID)
    assert item.citations[0].locator == "/source/paragraph/0"
    assert item.citations[0].quote == "quote"
    assessment.read_in_session.assert_called_once_with(
        knowledge.session, knowledge.scope, receipt.assessment_id
    )
    assert "private-preparation-marker" not in result.model_dump_json()
    assert "tenant_id" not in result.model_dump_json()


def test_missing_selection_keeps_all_200_components_unknown_without_a_search_claim():
    raw = json.dumps(
        {"components": [{"ecosystem": "npm", "package_name": "x", "version": None}] * 200}
    )
    payload = parse_public_stack_request(raw.encode())
    assessment, knowledge = fixture_services(fixture_receipt())
    result = stack_current_assessments(payload, (None,) * 200, assessment, knowledge)
    assert len(result.results) == 200
    assert all(item.status == "insufficient_evidence" for item in result.results)
    assert all(item.reason_code == "assessment_not_available" for item in result.results)
    assert all(item.freshness == "unknown" and not item.citations for item in result.results)
    assessment.read_in_session.assert_not_called()
    assert result.limitations == (
        "selected_assessments_do_not_prove_complete_rule_or_risk_coverage",
    )


@pytest.mark.parametrize("freshness", ["stale", "unknown"])
def test_invalidated_conclusion_is_not_returned_as_current_applicability(freshness):
    receipt = fixture_receipt(AssessmentStatus.SUPPORTED_APPLICABILITY, freshness=freshness)
    assessment, knowledge = fixture_services(receipt)
    result = stack_current_assessments(
        fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
    )
    assert result.results[0].status == "insufficient_evidence"
    assert result.results[0].freshness == freshness and not result.results[0].citations
    knowledge.read_evidence.assert_not_called()


@pytest.mark.parametrize(
    "updates",
    [
        dict(version="2.0"),
        dict(ecosystem="npm"),
        dict(package_name="another"),
        dict(purl="pkg:pypi/another@1.0"),
        dict(component_id=str(UUID(int=99))),
    ],
)
def test_component_selection_is_bound_to_the_real_frozen_asset_snapshot(updates):
    receipt = fixture_receipt()
    assessment, knowledge = fixture_services(receipt)
    with pytest.raises(PublicWriteMappingError, match="component_assessment_binding_mismatch"):
        stack_current_assessments(
            fixture_request(**updates), (UUID(receipt.assessment_id),), assessment, knowledge
        )
    knowledge.read_evidence.assert_not_called()


@pytest.mark.parametrize("error", [CrossTenantAccessError, PermissionDeniedError])
def test_current_pg_permission_or_visibility_failure_propagates(error):
    receipt = fixture_receipt()
    assessment, knowledge = fixture_services(receipt)
    assessment.read_in_session.side_effect = error("unit-only-denial")
    with pytest.raises(error):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )
    knowledge.read_evidence.assert_not_called()


def test_viewer_and_missing_selection_count_stop_before_the_pg_service():
    receipt = fixture_receipt()
    assessment, knowledge = fixture_services(receipt)
    with pytest.raises(PublicWriteMappingError, match="component_selection_count_mismatch"):
        stack_current_assessments(fixture_request(), (), assessment, knowledge)
    knowledge.scope = AccessScope.for_authenticated_user(
        "unit-viewer", "fixture-tenant", Role.VIEWER
    )
    with pytest.raises(PermissionDeniedError):
        stack_current_assessments(fixture_request(), (None,), assessment, knowledge)
    assessment.read_in_session.assert_not_called()


@pytest.mark.parametrize(
    "updates",
    [
        dict(verified_at=None),
        dict(revision_id=UUID(int=99)),
        dict(quote_text="changed"),
        dict(quote_sha256="0" * 64),
        dict(source_uri=None),
    ],
)
def test_current_evidence_verification_revision_quote_and_hash_are_rechecked(updates):
    receipt = fixture_receipt()
    assessment, knowledge = fixture_services(receipt)
    knowledge.read_evidence.return_value = knowledge.read_evidence.return_value.model_copy(
        update=updates
    )
    with pytest.raises(PublicWriteMappingError, match="assessment_evidence_changed"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )


def test_definitive_receipt_without_support_and_missing_locator_are_rejected():
    receipt = fixture_receipt(AssessmentStatus.EXCLUDED_WITH_EVIDENCE)
    assessment, knowledge = fixture_services(receipt)
    knowledge.session.scalar.return_value = None
    with pytest.raises(PublicWriteMappingError, match="assessment_locator_unavailable"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )
    unsupported = receipt.model_copy(
        update={
            "prepared": receipt.prepared.model_copy(
                update={"inputs": receipt.prepared.inputs.model_copy(update={"supports": ()})}
            )
        }
    )
    assessment.read_in_session.return_value = unsupported
    with pytest.raises(PublicWriteMappingError, match="definitive_assessment_support_unavailable"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )


def test_question_adapter_uses_the_shared_service_and_preserves_replay_key_and_errors():
    payload = parse_public_ask_request(
        json.dumps(
            {"question": "fixture only", "mode": "library", "event_ids": [str(uuid4())]}
        ).encode()
    )
    answer = QuestionAnswerResponse(
        answer_id=uuid4(),
        answer_text="fixture-only-service-output",
        claims=(),
        citations=(),
        limitations=("synthetic unit service output",),
        freshness="unknown",
        data_mode="fixture",
        started_at=STAMP,
        completed_at=STAMP,
        latency_milliseconds=0,
    )
    service = Mock(spec=GroundedQuestionService)
    service.ask.return_value = answer
    provider = Mock(return_value=FIXTURE_SCOPE)
    for _ in range(2):
        assert (
            ask_current_question(
                service, payload, provider, "unit-replay-key", session_token="unit-cookie"
            )
            == answer
        )
    assert service.ask.call_args.kwargs == {"session_token": "unit-cookie"}
    assert service.ask.call_args.args == (payload, provider, "unit-replay-key")
    assert service.ask.call_count == 2 and answer.data_mode == "fixture"
    service.ask.side_effect = QuestionFailure("unit_model_unavailable")
    with pytest.raises(QuestionFailure):
        ask_current_question(
            service, payload, provider, "unit-replay-key", session_token="unit-cookie"
        )


@pytest.mark.parametrize("key", ["", "space key", "k" * 201, "key\n"])
def test_question_key_validation_stops_before_shared_service(key):
    service = Mock(spec=GroundedQuestionService)
    payload = parse_public_ask_request(b'{"question":"fixture","mode":"auto"}')
    with pytest.raises(ValueError, match="public operation key is invalid"):
        ask_current_question(
            service, payload, lambda: FIXTURE_SCOPE, key, session_token="unit-cookie"
        )
    service.ask.assert_not_called()


def test_shared_assessment_read_uses_the_exact_open_transaction_and_current_scope(monkeypatch):
    engine = create_engine("sqlite://")
    service = AssessmentService(engine, "unit-cookie", Mock())
    session = Mock(spec=Session)
    session.in_transaction.return_value = True
    session.connection.return_value.engine = engine
    session.execute.return_value.mappings.return_value.first.return_value = {"unit": "row"}
    scope_lock = Mock(return_value=FIXTURE_SCOPE)
    monkeypatch.setattr(
        "ai_intel.assessment.assessment_service.lock_authenticated_scope", scope_lock
    )
    receipt = fixture_receipt()
    service._read_result = Mock(return_value=receipt)
    assert service.read_in_session(session, FIXTURE_SCOPE, receipt.assessment_id) == receipt
    scope_lock.assert_called_once()
    assert scope_lock.call_args.args[0] is session.connection.return_value
    service._read_result.assert_called_once_with(session, FIXTURE_SCOPE, {"unit": "row"})
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    engine.dispose()


@pytest.mark.parametrize(
    "cause", ["no_transaction", "other_engine", "scope_changed", "not_visible"]
)
def test_shared_assessment_read_fails_closed_at_transaction_auth_and_tenant_boundaries(
    monkeypatch, cause
):
    engine = create_engine("sqlite://")
    service = AssessmentService(engine, "unit-cookie", Mock())
    session = Mock(spec=Session)
    session.in_transaction.return_value = cause != "no_transaction"
    session.connection.return_value.engine = engine if cause != "other_engine" else Mock()
    session.execute.return_value.mappings.return_value.first.return_value = None
    current = FIXTURE_SCOPE
    if cause == "scope_changed":
        current = AccessScope.for_authenticated_user(
            "another-owner", "fixture-tenant", Role.ANALYST
        )
    monkeypatch.setattr(
        "ai_intel.assessment.assessment_service.lock_authenticated_scope",
        Mock(return_value=current),
    )
    expected = {
        "no_transaction": ValueError,
        "other_engine": ValueError,
        "scope_changed": PermissionDeniedError,
        "not_visible": CrossTenantAccessError,
    }[cause]
    with pytest.raises(expected):
        service.read_in_session(session, FIXTURE_SCOPE, str(UUID(int=44)))
    engine.dispose()


@pytest.mark.parametrize(
    "field,value",
    [
        ("asset_id", "another-asset"),
        ("asset_snapshot_id", "another-snapshot"),
        ("event_id", "another-event"),
        ("rule_id", "another-rule"),
        ("rule_version", 2),
    ],
)
def test_receipt_primary_identities_must_match_the_frozen_inputs(field, value):
    receipt = fixture_receipt().model_copy(update={field: value})
    assessment, knowledge = fixture_services(receipt)
    with pytest.raises(PublicWriteMappingError, match="assessment_receipt_identity_mismatch"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )
    knowledge.read_evidence.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("rule_id", "another-rule"),
        ("rule_version", 2),
        ("asset_snapshot_id", "another-snapshot"),
        ("status", AssessmentStatus.SUPPORTED_APPLICABILITY),
    ],
)
def test_receipt_rule_result_must_match_the_assessment_identity_and_four_state(field, value):
    receipt = fixture_receipt()
    receipt = receipt.model_copy(
        update={"rule_result": receipt.rule_result.model_copy(update={field: value})}
    )
    assessment, knowledge = fixture_services(receipt)
    with pytest.raises(PublicWriteMappingError, match="assessment_rule_result_mismatch"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )
    knowledge.read_evidence.assert_not_called()


def test_unknown_reason_cannot_be_projected_as_supported_applicability():
    receipt = fixture_receipt(AssessmentStatus.SUPPORTED_APPLICABILITY)
    receipt = receipt.model_copy(
        update={
            "rule_result": receipt.rule_result.model_copy(
                update={
                    "evaluation_tree": receipt.rule_result.evaluation_tree.model_copy(
                        update={"reason_code": "no_match"}
                    )
                }
            )
        }
    )
    assessment, knowledge = fixture_services(receipt)
    with pytest.raises(
        ValueError, match="missing or unsupported inputs require insufficient evidence"
    ):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )


@pytest.mark.parametrize(
    "selection",
    [
        "unrelated_component",
        "multiple_component_scopes",
        "asset_only_condition",
        "observed_path",
        "research_prerequisites",
    ],
)
def test_whole_asset_or_other_rule_scope_cannot_confirm_this_component(selection):
    receipt = fixture_receipt(AssessmentStatus.SUPPORTED_APPLICABILITY)
    rule = receipt.prepared.inputs.rule
    if selection in {"observed_path", "research_prerequisites"}:
        rule = rule.model_copy(update={"rule_kind": selection})
    else:
        condition = dict(
            node_id="leaf", kind="component_matches", ecosystem="PyPI", package_key="other"
        )
        if selection == "asset_only_condition":
            condition = dict(
                node_id="leaf",
                kind="configuration_equals",
                field="trust_remote_code",
                expected=True,
            )
        elif selection == "multiple_component_scopes":
            condition = dict(
                node_id="root",
                kind="any_of",
                children=[
                    dict(
                        node_id="requested",
                        kind="component_matches",
                        ecosystem="PyPI",
                        package_key="fixture",
                    ),
                    dict(
                        node_id="other",
                        kind="component_matches",
                        ecosystem="PyPI",
                        package_key="other",
                    ),
                ],
            )
        rule = rule.model_copy(update={"condition_ast": parse_condition_tree(condition)})
    prepared = receipt.prepared.model_copy(
        update={"inputs": receipt.prepared.inputs.model_copy(update={"rule": rule})}
    )
    receipt = receipt.model_copy(
        update={
            "prepared": prepared,
            "rule_result": receipt.rule_result.model_copy(
                update={
                    "rule_kind": rule.rule_kind,
                    "condition_sha256": condition_digest(rule.condition_ast),
                }
            ),
        }
    )
    assessment, knowledge = fixture_services(receipt)
    result = stack_current_assessments(
        fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
    )
    assert result.results[0].status == AssessmentStatus.INSUFFICIENT_EVIDENCE
    assert result.results[0].reason_code == "unsupported_rule" and not result.results[0].citations
    assert "selected_rule_does_not_establish_component_software_applicability" in result.limitations
    knowledge.read_evidence.assert_not_called()


def test_rule_condition_hash_must_match_the_frozen_receipt():
    receipt = fixture_receipt()
    receipt = receipt.model_copy(
        update={
            "rule_result": receipt.rule_result.model_copy(update={"condition_sha256": "0" * 64})
        }
    )
    assessment, knowledge = fixture_services(receipt)
    with pytest.raises(PublicWriteMappingError, match="assessment_rule_result_mismatch"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessment, knowledge
        )


@pytest.mark.parametrize(
    "whole_asset_status",
    [AssessmentStatus.SUPPORTED_APPLICABILITY, AssessmentStatus.CONFLICTING_EVIDENCE],
)
def test_mixed_versions_of_one_package_do_not_borrow_the_whole_asset_verdict(whole_asset_status):
    receipt = fixture_receipt(whole_asset_status)
    original = receipt.prepared.asset_snapshot.components[0]
    other = original.model_copy(update={"component_id": str(UUID(int=94)), "version": "3.0"})
    snapshot = receipt.prepared.asset_snapshot.model_copy(update={"components": (original, other)})
    receipt = receipt.model_copy(
        update={"prepared": receipt.prepared.model_copy(update={"asset_snapshot": snapshot})}
    )
    assessment, knowledge = fixture_services(receipt)
    requested = fixture_request(version="3.0", component_id=str(UUID(int=94)))
    result = stack_current_assessments(
        requested, (UUID(receipt.assessment_id),), assessment, knowledge
    )
    assert result.results[0].component.version == "3.0"
    assert result.results[0].status == AssessmentStatus.INSUFFICIENT_EVIDENCE
    assert result.results[0].reason_code == "unsupported_rule" and not result.results[0].citations
    knowledge.read_evidence.assert_not_called()


def test_equal_version_instances_keep_duplicate_request_components_without_shrinking_coverage():
    receipt = fixture_receipt(AssessmentStatus.SUPPORTED_APPLICABILITY)
    original = receipt.prepared.asset_snapshot.components[0]
    same_version = original.model_copy(update={"component_id": str(UUID(int=95))})
    snapshot = receipt.prepared.asset_snapshot.model_copy(
        update={"components": (original, same_version)}
    )
    receipt = receipt.model_copy(
        update={"prepared": receipt.prepared.model_copy(update={"asset_snapshot": snapshot})}
    )
    assessment, knowledge = fixture_services(receipt)
    request = parse_public_stack_request(
        json.dumps(
            {
                "components": [
                    {
                        "ecosystem": "PyPI",
                        "package_name": "fixture",
                        "version": "1.0",
                        "component_id": str(UUID(int=3)),
                    },
                    {
                        "ecosystem": "PyPI",
                        "package_name": "fixture",
                        "version": "1.0",
                        "component_id": str(UUID(int=95)),
                    },
                ]
            }
        ).encode()
    )
    result = stack_current_assessments(
        request, (UUID(receipt.assessment_id),) * 2, assessment, knowledge
    )
    assert len(result.results) == 2
    assert [item.component.component_id for item in result.results] == [UUID(int=3), UUID(int=95)]
    assert all(item.status == AssessmentStatus.SUPPORTED_APPLICABILITY for item in result.results)
    assert assessment.read_in_session.call_count == 2
