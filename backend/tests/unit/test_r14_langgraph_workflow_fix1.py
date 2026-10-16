"""Independent typed conflict negative with explicit isolated IO fixtures, never live."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from ai_intel.api.knowledge_contracts import CitationProjection, ClaimSummary
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import ClaimOrigin, ClaimStatus
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import InvestigationRequest
from ai_intel.investigation.workflow_service import _initial_state, _WorkflowRuntime
from ai_intel.workers.executor import JobExecutionContext


def test_review_disputed_claim_stops_qa_before_model_generation(monkeypatch):
    claim = ClaimSummary(
        claim_id=uuid4(),
        predicate="affected_versions",
        display_value="contradictory range",
        origin=ClaimOrigin.SOURCE_EXPLICIT,
        status=ClaimStatus.DISPUTED,
        source_revision_id=uuid4(),
        evidence_ids=(),
    )
    service = SimpleNamespace(data_mode="fixture")
    context = JobExecutionContext(str(uuid4()), "review-fixture", 1, "review-fixture-tenant")
    runtime = _WorkflowRuntime(service, None, context)
    runtime.scope = AccessScope.for_authenticated_user(
        "review-fixture-user", "review-fixture-tenant", Role.ANALYST
    )
    runtime.request = InvestigationRequest(
        question="What is the disputed version range?", event_id=uuid4(), evidence_refs=()
    )
    runtime.input_sha256 = "a" * 64

    @contextmanager
    def transaction():
        yield None

    monkeypatch.setattr(runtime, "transaction", transaction)
    monkeypatch.setattr(runtime, "guard", lambda **kwargs: None)
    monkeypatch.setattr(runtime, "lookup", lambda key: None)
    monkeypatch.setattr(runtime, "reserve", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, "complete_operation", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        KnowledgeReadService,
        "event_detail",
        lambda self, event_id: SimpleNamespace(claims=(claim,), dimensions=()),
    )
    state = runtime.run_role(AgentRole.ENRICHER, _initial_state(runtime.input_sha256))
    assert state["stop_reason"] == "critical_conflict"
    projection = CitationProjection(
        evidence_id=uuid4(),
        revision_id=uuid4(),
        quote="explicit fixture support",
        locator="text:0:24",
        source_uri="https://example.invalid/fixture-conflict",
    )
    monkeypatch.setattr(runtime, "projections", lambda state: (projection,))

    def unexpected_model(*args, **kwargs):
        raise AssertionError("disputed claim must stop generation")

    monkeypatch.setattr(runtime, "model", unexpected_model)
    state = runtime.run_role(AgentRole.QA, state)
    assert state["receipts"][-1]["reason_code"] == "critical_conflict"
    state = runtime.run_role(AgentRole.REPORTER, state)
    assert state["stop_reason"] == "critical_conflict" and state["draft"] is None


def test_reporter_preserves_unresolved_operation_reason(monkeypatch):
    runtime = _WorkflowRuntime(
        SimpleNamespace(data_mode="fixture"),
        None,
        JobExecutionContext(str(uuid4()), "fixture-worker", 1, None),
    )
    runtime.input_sha256 = "b" * 64
    monkeypatch.setattr(runtime, "guard", lambda **kwargs: None)
    monkeypatch.setattr(runtime, "lookup", lambda key: None)
    monkeypatch.setattr(runtime, "reserve", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, "complete_operation", lambda *args, **kwargs: None)
    state = _initial_state(runtime.input_sha256)
    state["stop_reason"] = "operation_outcome_unknown"
    state = runtime.run_role(AgentRole.REPORTER, state)
    assert state["stop_reason"] == "operation_outcome_unknown" and state["draft"] is None
