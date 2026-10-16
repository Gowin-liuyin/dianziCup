"""Explicit fixture readers isolate request-local budgets without claiming external live IO."""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from uuid import UUID, uuid4

import pytest

from ai_intel.api.authentication import Principal
from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.tool_contracts import ReadEvidenceArguments, ToolName
from ai_intel.investigation.tool_gateway import (
    BudgetLimits,
    EvidenceRead,
    GatewayStoppedError,
    ToolGateway,
)

NOW = datetime(2026, 10, 16, tzinfo=UTC)
GOAL_ID, EVENT_ID, SPAN_ID, REVISION_ID = (uuid4() for _ in range(4))


def evidence_response(
    quote: str = "fixture evidence", *, verified: bool = True
) -> EvidenceResponse:
    return EvidenceResponse(
        span_id=SPAN_ID,
        revision_id=REVISION_ID,
        block_id=uuid4(),
        start_offset=0,
        end_offset=len(quote),
        quote_text=quote,
        quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
        locator_kind="text" if verified else "legacy_unverified",
        page_number=None,
        json_pointer=None,
        verified_at=NOW if verified else None,
        source_uri=None,
        source_published_at=None,
        source_modified_at=None,
        first_observed_at=NOW,
        ingested_at=NOW,
        data_mode="fixture",
    )


class FixtureEvidenceReader:
    data_mode = "fixture"

    def __init__(self) -> None:
        self.calls = 0
        self.scopes: list[AccessScope] = []
        self.outcome = EvidenceRead(evidence_response(), True)
        self.error: BaseException | None = None
        self.started: Event | None = None
        self.release: Event | None = None

    def read_evidence(
        self,
        principal: Principal,
        scope: AccessScope,
        arguments: ReadEvidenceArguments,
        deadline_monotonic: float,
    ) -> EvidenceRead:
        self.calls += 1
        self.scopes.append(scope)
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            assert self.release.wait(timeout=2)
        if self.error is not None:
            raise self.error
        return self.outcome


def limits(**changes: int | float) -> BudgetLimits:
    return BudgetLimits.model_validate(
        {
            "max_calls": 8,
            "max_concurrent_calls": 1,
            "max_request_bytes": 4096,
            "max_total_input_bytes": 32768,
            "max_result_bytes": 4096,
            "max_total_output_bytes": 32768,
            "deadline_monotonic": time.monotonic() + 10,
            **changes,
        }
    )


def gateway(reader: FixtureEvidenceReader | None = None, **changes: int | float) -> ToolGateway:
    return ToolGateway(
        Principal("fixture-user", "owner", Role.ANALYST),
        uuid4(),
        limits(**changes),
        evidence_reader=reader,
    )


def evidence_call(*, goal_id: UUID = GOAL_ID) -> bytes:
    return json.dumps(
        {
            "tool_name": "read_evidence",
            "goal_id": str(goal_id),
            "arguments": {
                "event_id": str(EVENT_ID),
                "evidence_id": str(SPAN_ID),
                "revision_id": str(REVISION_ID),
            },
        }
    ).encode()


def comparison_call(left: str | None = "1.10", right: str | None = "1.9") -> bytes:
    return json.dumps(
        {
            "tool_name": "compare_versions",
            "goal_id": str(GOAL_ID),
            "arguments": {
                "left_version": left,
                "right_version": right,
                "scheme": "pep440",
                "ecosystem": "PyPI",
            },
        }
    ).encode()


def test_t32_c01_evidence_trace_retains_identity_scope_time_and_fixture_marker() -> None:
    reader = FixtureEvidenceReader()
    subject = gateway(reader)
    result = subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert result.status == "succeeded" and result.data == reader.outcome.evidence
    assert result.evidence_ids == (SPAN_ID,) and result.observed_at == NOW
    assert result.searched_scope.event_id == EVENT_ID
    assert result.searched_scope.revision_id == REVISION_ID
    assert result.searched_scope.scope_kind == "tenant" and result.is_synthetic
    assert result.usage.service_calls == 1 and not result.usage.cached
    assert result.usage.result_bytes == len(result.model_dump_json().encode())
    assert subject.runs == (result,)


@pytest.mark.parametrize("agent_role", [AgentRole.TRIAGE, AgentRole.QA, AgentRole.CRITIC])
def test_t32_c02_public_research_roles_do_not_receive_private_scope(agent_role: AgentRole) -> None:
    reader = FixtureEvidenceReader()
    assert gateway(reader).execute(agent_role, evidence_call()).status == "succeeded"
    assert reader.scopes[0].tenant_id is None


def test_t32_c03_call_budget_exhaustion_prevents_service_io() -> None:
    reader = FixtureEvidenceReader()
    subject = gateway(reader, max_calls=1)
    assert subject.execute(AgentRole.ASSESSOR, evidence_call()).status == "succeeded"
    result = subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=uuid4()))
    assert result.status == "budget_exhausted" and result.error_code == "call_budget_exhausted"
    assert reader.calls == 1


def test_t32_c04_pure_result_replay_preserves_call_key_without_double_count() -> None:
    subject = gateway(max_calls=1)
    first = subject.execute(AgentRole.ASSESSOR, comparison_call())
    second = subject.execute(AgentRole.CRITIC, comparison_call())
    assert first.status == second.status == "succeeded"
    assert first.data == second.data and first.call_key == second.call_key
    assert first.tool_run_id != second.tool_run_id
    assert second.usage.cached and second.usage.service_calls == 0


@pytest.mark.parametrize("supported,verified", [(False, True), (True, False), (False, False)])
def test_historical_or_unverified_evidence_remains_partial(supported: bool, verified: bool) -> None:
    reader = FixtureEvidenceReader()
    reader.outcome = EvidenceRead(evidence_response(verified=verified), supported)
    result = gateway(reader).execute(AgentRole.ASSESSOR, evidence_call())
    assert result.status == "partial" and result.error_code == "evidence_not_current_supported"
    assert result.data is not None and result.evidence_ids == (SPAN_ID,)


def test_t32_c05_failed_input_is_terminal_across_public_roles_and_error_is_redacted() -> None:
    reader = FixtureEvidenceReader()
    reader.error = ValueError("password=fixture-sensitive-error-material")
    subject = gateway(reader)
    first = subject.execute(AgentRole.QA, evidence_call())
    second = subject.execute(AgentRole.CRITIC, evidence_call())
    assert first.status == second.status == "failed" and reader.calls == 1
    assert first.error_code == "tool_output_invalid" and second.usage.cached
    assert "fixture-sensitive" not in json.dumps(
        [run.model_dump(mode="json") for run in subject.runs]
    )


@pytest.mark.parametrize("supported", [True, False])
def test_evidence_replay_revalidates_acl_for_success_and_partial(supported: bool) -> None:
    reader = FixtureEvidenceReader()
    reader.outcome = EvidenceRead(evidence_response(), supported)
    subject = gateway(reader)
    assert subject.execute(AgentRole.ASSESSOR, evidence_call()).data is not None
    reader.error = CrossTenantAccessError("resource not found")
    replay = subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert reader.calls == 2 and replay.status == "denied" and replay.data is None
    assert replay.evidence_ids == () and not replay.usage.cached


def test_missing_executor_is_not_configured_and_never_an_empty_search() -> None:
    subject = gateway()
    result = subject.execute(AgentRole.QA, evidence_call())
    assert result.status == "not_configured" and result.data is None
    assert ToolName.READ_EVIDENCE not in subject.configured_tools


@pytest.mark.parametrize("left,right", [(None, "1.0"), ("invalid", "1.0")])
def test_missing_or_invalid_version_is_unknown_without_fabricated_ordering(
    left: str | None,
    right: str | None,
) -> None:
    result = gateway().execute(AgentRole.ASSESSOR, comparison_call(left, right))
    assert result.status == "partial" and result.data is not None
    assert not isinstance(result.data, EvidenceResponse) and result.data.ordering is None
    assert result.data.status == "unknown"


def test_deadline_exhaustion_prevents_dispatch() -> None:
    reader = FixtureEvidenceReader()
    result = gateway(reader, deadline_monotonic=time.monotonic() - 1).execute(
        AgentRole.ASSESSOR, evidence_call()
    )
    assert result.status == "budget_exhausted" and result.error_code == "deadline_exhausted"
    assert reader.calls == 0


def test_concurrent_call_and_duplicate_are_rejected_without_waiting() -> None:
    reader = FixtureEvidenceReader()
    reader.started, reader.release = Event(), Event()
    subject = gateway(reader)
    with ThreadPoolExecutor(max_workers=1) as workers:
        first = workers.submit(subject.execute, AgentRole.ASSESSOR, evidence_call())
        assert reader.started.wait(timeout=2)
        duplicate = subject.execute(AgentRole.ASSESSOR, evidence_call())
        different = subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=uuid4()))
        reader.release.set()
        assert first.result(timeout=2).status == "succeeded"
    assert duplicate.error_code == "duplicate_inflight"
    assert different.error_code == "concurrency_exhausted" and reader.calls == 1


def test_output_budget_is_reserved_before_service_dispatch_and_stops_replays() -> None:
    reader = FixtureEvidenceReader()
    subject = gateway(reader, max_result_bytes=4096, max_total_output_bytes=1024)
    with pytest.raises(GatewayStoppedError, match="output_budget_exhausted"):
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    with pytest.raises(GatewayStoppedError):
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert reader.calls == 0


def test_unexpected_tool_failure_is_explicit_redacted_and_terminal() -> None:
    reader = FixtureEvidenceReader()
    reader.error = RuntimeError("fixture private internal material")
    subject = gateway(reader)
    first = subject.execute(AgentRole.QA, evidence_call())
    replay = subject.execute(AgentRole.CRITIC, evidence_call())
    assert first.status == replay.status == "failed"
    assert first.error_code == "tool_execution_failed" and first.is_synthetic
    assert reader.calls == 1 and replay.usage.cached
    assert "private internal" not in first.model_dump_json()


def test_denied_calls_cannot_spend_an_active_call_output_reservation() -> None:
    reader = FixtureEvidenceReader()
    reader.started, reader.release = Event(), Event()
    subject = gateway(reader, max_result_bytes=4096, max_total_output_bytes=4096)
    with ThreadPoolExecutor(max_workers=1) as workers:
        first = workers.submit(subject.execute, AgentRole.ASSESSOR, evidence_call())
        assert reader.started.wait(timeout=2)
        with pytest.raises(GatewayStoppedError, match="output_budget_exhausted"):
            subject.execute(AgentRole.QA, b"invalid")
        reader.release.set()
        result = first.result(timeout=2)
    assert result.status == "succeeded" and result.usage.result_bytes <= 4096


def test_per_tool_deadline_is_supplied_to_the_trusted_reader() -> None:
    reader = FixtureEvidenceReader()
    received: list[float] = []
    original = reader.read_evidence

    def capture(
        principal: Principal,
        scope: AccessScope,
        arguments: ReadEvidenceArguments,
        deadline_monotonic: float,
    ) -> EvidenceRead:
        received.append(deadline_monotonic)
        return original(principal, scope, arguments, deadline_monotonic)

    reader.read_evidence = capture
    before = time.monotonic()
    assert gateway(reader).execute(AgentRole.QA, evidence_call()).status == "succeeded"
    assert before < received[0] <= time.monotonic() + 5
