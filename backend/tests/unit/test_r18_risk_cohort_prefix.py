"""Strict offline cohorts prove bounded parent locking before the actual receipt seam."""

from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from tests.unit.test_public_write_adapters import fixture_request
from tests.unit.test_r18_current_risk_summary import fixture_receipt, producer_fixture
from tests.unit.test_r18_public_component_selector import selection_fixture

from ai_intel.api.public_risk_summary import (
    MAX_RULE_INPUTS,
    _assessment_cohort,
    _cohort_parent_refs,
    _lock_assessment_cohort,
    build_current_stack_envelope,
)
from ai_intel.api.public_write_adapters import PublicWriteMappingError
from ai_intel.assessment.rule_persistence import RulePersistenceError
from ai_intel.domain.access import CrossTenantAccessError


def cohort_row(receipt):
    row = {
        field: getattr(receipt, field)
        for field in (
            "assessment_id",
            "tenant_id",
            "asset_id",
            "asset_snapshot_id",
            "event_id",
            "rule_id",
            "rule_version",
        )
    }
    row["result_payload"] = receipt.model_dump(mode="json")
    return row


def source_parent(source=1, revision=2, *, tenant=None):
    return {
        "source_id": str(UUID(int=source)),
        "document_id": str(UUID(int=source + 100)),
        "revision_id": str(UUID(int=revision)),
        "content_hash": "a" * 64,
        **{
            prefix + key: value
            for prefix in ("", "document_", "source_")
            for key, value in (
                ("visibility", "public" if tenant is None else "tenant"),
                ("tenant_id", tenant),
            )
        },
    }


def compiled_queries(knowledge):
    return [
        call.args[0].compile(dialect=postgresql.dialect())
        for call in knowledge.session.execute.call_args_list
    ]


def publication_index(queries):
    return next(
        index
        for index, query in enumerate(queries)
        if "knowledge-publication:public" in query.params.values()
    )


def test_cohort_uses_every_exact_candidate_without_latest_or_early_row_lock():
    _service, knowledge = selection_fixture()
    knowledge.session.execute.return_value.mappings.return_value = []
    payload = fixture_request()
    payload = payload.model_copy(
        update={
            "components": (
                payload.components[0],
                fixture_request(version="2.0").components[0],
            )
        }
    )
    assert _assessment_cohort(payload, knowledge) == ()
    query = compiled_queries(knowledge)[0]
    assert MAX_RULE_INPUTS + 1 in query.params.values()
    assert "FOR " not in str(query) and "created_at DESC" not in str(query)
    assert "assets.current_snapshot_id = asset_snapshots.snapshot_id" in str(query)
    assert "assessment_results.tenant_id = asset_snapshots.tenant_id" in str(query)
    assert knowledge.scope.tenant_id in query.params.values()
    for version in ("1.0", "2.0"):
        assert [
            {"ecosystem": "PyPI", "package_name": "fixture", "version": version}
        ] in query.params.values()


def test_no_supported_request_identity_means_no_candidate_query():
    _service, knowledge = selection_fixture()
    assert _assessment_cohort(fixture_request(version=None), knowledge) == ()
    knowledge.session.execute.assert_not_called()


def test_both_assets_and_sources_are_locked_before_first_publication_and_receipt(monkeypatch):
    first, service, knowledge = producer_fixture(monkeypatch)
    second = first.model_copy(
        update={
            "assessment_id": str(UUID(int=801)),
            "asset_id": str(UUID(int=802)),
        }
    )
    rows = (cohort_row(first), cohort_row(second))
    parents = (
        ("source-z", "document-z", "revision-z", "a" * 64),
        ("source-a", "document-a", "revision-a", "b" * 64),
    )
    monkeypatch.setattr("ai_intel.api.public_risk_summary._assessment_cohort", lambda *args: rows)
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._cohort_parent_refs", lambda *args: parents
    )
    actual_seam_observations = []

    def read_receipt(session, scope, identifier):
        actual_seam_observations.append(compiled_queries(knowledge))
        return first

    service.read_in_session.side_effect = read_receipt
    envelope = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert envelope.risk_summary.coverage == "complete"
    assert len(actual_seam_observations) == 3
    queries = actual_seam_observations[0]
    publication = publication_index(queries)
    asset_query = next(query for query in queries if "FROM assets" in str(query))
    assert sorted((first.asset_id, second.asset_id)) in asset_query.params.values()
    assert knowledge.scope.tenant_id in asset_query.params.values()
    source_locks = [
        value
        for query in queries[:publication]
        for value in query.params.values()
        if isinstance(value, str) and value.startswith("source:")
    ]
    assert source_locks == ["source:source-a", "source:source-z"]
    assert any(
        "FOR SHARE OF documents, document_revisions" in str(query)
        for query in queries[:publication]
    )
    assert any(
        "FROM content_objects" in str(query) and "FOR SHARE" in str(query)
        for query in queries[:publication]
    )
    assert not any(
        "source:" in str(value)
        for query in queries[publication:]
        for value in query.params.values()
    )


@pytest.mark.parametrize("field", ["asset_id", "rule_id", "event_id", "rule_version"])
def test_unbound_receipt_never_reaches_publication_or_actual_reader(monkeypatch, field):
    receipt, service, knowledge = producer_fixture(monkeypatch)
    row = cohort_row(receipt)
    row[field] = 999 if field == "rule_version" else str(UUID(int=999))
    monkeypatch.setattr("ai_intel.api.public_risk_summary._assessment_cohort", lambda *args: (row,))
    with pytest.raises(PublicWriteMappingError, match="risk_assessment_cohort_binding_mismatch"):
        build_current_stack_envelope(fixture_request(), service, knowledge)
    knowledge.session.execute.assert_not_called()
    service.read_in_session.assert_not_called()


@pytest.mark.parametrize("kind", ["candidate_limit", "source_limit", "rule_source_limit"])
def test_overflow_has_no_publication_or_receipt_and_cannot_be_negative(monkeypatch, kind):
    _receipt, service, knowledge = producer_fixture(monkeypatch)
    if kind == "candidate_limit":
        monkeypatch.setattr(
            "ai_intel.api.public_risk_summary._assessment_cohort",
            lambda *args: ({},) * (MAX_RULE_INPUTS + 1),
        )
    elif kind == "source_limit":
        monkeypatch.setattr(
            "ai_intel.api.public_risk_summary._cohort_parent_refs",
            lambda *args: (("source", "doc", "rev", "a" * 64),) * (MAX_RULE_INPUTS + 1),
        )
    else:
        monkeypatch.setattr(
            "ai_intel.api.public_risk_summary._cohort_parent_refs",
            Mock(side_effect=RulePersistenceError("source_roster_budget_exceeded")),
        )
    envelope = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert envelope.risk_summary.confirmation == "unknown"
    assert envelope.risk_summary.coverage == "unknown"
    assert envelope.risk_summary.unknown_component_indices == (0,)
    assert not envelope.risk_summary.findings
    service.read_in_session.assert_not_called()
    assert not any(
        "knowledge-publication:" in str(value)
        for query in compiled_queries(knowledge)
        for value in query.params.values()
    )


@pytest.mark.parametrize("change", ["new_candidate", "retired", "snapshot_changed", "overflow"])
def test_post_publication_candidate_change_never_backfills_asset_or_source(monkeypatch, change):
    receipt, service, knowledge = producer_fixture(monkeypatch)
    row = cohort_row(receipt)
    if change == "retired":
        final = ()
    elif change == "overflow":
        final = (row,) * (MAX_RULE_INPUTS + 1)
    elif change == "new_candidate":
        final = (row, {**row, "assessment_id": str(UUID(int=800))})
    else:
        final = ({**row, "asset_snapshot_id": str(UUID(int=800))},)
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._assessment_cohort", Mock(side_effect=[(row,), final])
    )
    envelope = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert envelope.risk_summary.confirmation == "unknown"
    assert "risk_assessment_cohort_changed" in envelope.result.limitations
    service.read_in_session.assert_not_called()
    queries = compiled_queries(knowledge)
    assert not any("FOR " in str(query) for query in queries[publication_index(queries) + 2 :])


@pytest.mark.parametrize(
    "change", ["new_grade_source", "revision", "content_hash", "overflow", "rule_overflow"]
)
def test_post_publication_parent_change_is_unknown_without_new_parent_lock(monkeypatch, change):
    _receipt, service, knowledge = producer_fixture(monkeypatch)
    initial = (("source-a", "doc-a", "rev-a", "a" * 64),)
    if change == "new_grade_source":
        final = (*initial, ("source-b", "doc-b", "rev-b", "b" * 64))
    elif change == "revision":
        final = (("source-a", "doc-a", "rev-b", "a" * 64),)
    elif change == "content_hash":
        final = (("source-a", "doc-a", "rev-a", "b" * 64),)
    elif change == "overflow":
        final = initial * (MAX_RULE_INPUTS + 1)
    else:
        final = RulePersistenceError("source_roster_budget_exceeded")
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._cohort_parent_refs", Mock(side_effect=[initial, final])
    )
    envelope = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert envelope.risk_summary.confirmation == "unknown"
    assert "risk_source_cohort_changed" in envelope.result.limitations
    service.read_in_session.assert_not_called()
    queries = compiled_queries(knowledge)
    assert not any("source:source-b" in query.params.values() for query in queries)
    assert not any("FOR " in str(query) for query in queries[publication_index(queries) + 2 :])


def test_only_expected_source_budget_is_converted_to_unknown(monkeypatch):
    _receipt, _service, knowledge = producer_fixture(monkeypatch)
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._cohort_parent_refs",
        Mock(side_effect=RulePersistenceError("unexpected_storage_problem")),
    )
    with pytest.raises(RulePersistenceError, match="unexpected_storage_problem"):
        _lock_assessment_cohort(fixture_request(), knowledge)


def test_rule_closure_and_inactive_grade_primary_are_both_in_the_prefix(monkeypatch):
    receipt = fixture_receipt()
    _service, knowledge = selection_fixture(receipt)
    rule = receipt.prepared.inputs.rule
    monkeypatch.setattr("ai_intel.api.public_risk_summary.read_rule", lambda *args: {})
    monkeypatch.setattr("ai_intel.api.public_risk_summary.stored_rule", lambda row: rule)
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._all_source_rows", lambda *args: (source_parent(),)
    )
    grade = source_parent(3, 4)
    knowledge.session.execute.return_value.mappings.return_value = [grade]
    parents = _cohort_parent_refs((cohort_row(receipt),), knowledge)
    assert {item[0] for item in parents} == {str(UUID(int=1)), str(UUID(int=3))}
    query = compiled_queries(knowledge)[0]
    assert "claims.source_revision_id" in str(query)
    assert "event_documents" not in str(query)
    assert "FOR " not in str(query) and query.params["param_1"] == MAX_RULE_INPUTS + 1
    assert receipt.event_id in next(
        value
        for value in query.params.values()
        if isinstance(value, list) and receipt.event_id in value
    )


def test_cross_tenant_grade_parent_is_refused_before_any_lock(monkeypatch):
    receipt = fixture_receipt()
    _service, knowledge = selection_fixture(receipt)
    monkeypatch.setattr("ai_intel.api.public_risk_summary.read_rule", lambda *args: {})
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary.stored_rule", lambda row: receipt.prepared.inputs.rule
    )
    monkeypatch.setattr("ai_intel.api.public_risk_summary._all_source_rows", lambda *args: ())
    knowledge.session.execute.return_value.mappings.return_value = [
        source_parent(tenant="other-tenant")
    ]
    with pytest.raises(CrossTenantAccessError):
        _cohort_parent_refs((cohort_row(receipt),), knowledge)
    assert all("FOR " not in str(query) for query in compiled_queries(knowledge))
