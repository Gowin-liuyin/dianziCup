"""Reviewer-authored adverse inputs; expected values follow contracts rather than implementation."""

import json
from asyncio import CancelledError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_r14_tool_gateway import (
    FixtureEvidenceReader,
    comparison_call,
    evidence_call,
    evidence_response,
    gateway,
    limits,
)

from ai_intel.api.authentication import Principal
from ai_intel.domain.access import Role
from ai_intel.domain.enums import ToolStatus
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.tool_gateway import EvidenceRead, GatewayStoppedError, ToolGateway


def test_review_budget_result_uses_the_frozen_domain_tool_status() -> None:
    reader = FixtureEvidenceReader()
    subject = gateway(reader, max_calls=1)
    subject.execute(AgentRole.ASSESSOR, evidence_call())
    blocked = subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=uuid4()))
    assert reader.calls == 1
    assert ToolStatus(blocked.status) == ToolStatus.BUDGET_EXHAUSTED


@pytest.mark.parametrize(
    "role",
    [
        AgentRole.ORCHESTRATOR,
        AgentRole.COLLECTOR,
        AgentRole.TRIAGE,
        AgentRole.ENRICHER,
        AgentRole.GRAPH_WRITER,
        AgentRole.QA,
        AgentRole.REPORTER,
    ],
)
def test_review_disallowed_pure_comparison_never_spends_a_service_call(role) -> None:
    result = gateway().execute(role, comparison_call())
    assert result.status == "denied" and result.error_code == "role_tool_denied"
    assert result.usage.service_calls == 0 and result.data is None


@pytest.mark.parametrize(
    "payload_update",
    [
        {"tool_name": "read_evidence; SELECT pg_sleep(10)"},
        {
            "tool_name": "read_evidence",
            "arguments": {
                "event_id": str(uuid4()),
                "evidence_id": str(uuid4()),
                "revision_id": str(uuid4()),
                "tool_name": "shell",
            },
        },
        {"tool_name": "read_evidence", "role": "assessor"},
    ],
)
def test_review_allowlist_and_nested_authority_injection_remain_closed(payload_update) -> None:
    payload = json.loads(evidence_call())
    payload.update(payload_update)
    reader = FixtureEvidenceReader()
    result = gateway(reader).execute(AgentRole.QA, json.dumps(payload).encode())
    assert result.status == "denied" and result.error_code == "invalid_tool_input"
    assert reader.calls == 0 and result.data is None


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(17), CancelledError()])
def test_review_control_exceptions_propagate_and_release_output_reservation(error) -> None:
    reader = FixtureEvidenceReader()
    reader.error = error
    subject = gateway(reader, max_result_bytes=4096, max_total_output_bytes=4096)
    with pytest.raises(type(error)):
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert subject.runs == ()
    reader.error = None
    assert subject.execute(AgentRole.ASSESSOR, evidence_call()).status == "succeeded"


def test_review_parallel_results_do_not_share_mutable_budget_or_result_objects() -> None:
    rendezvous = Barrier(2)

    class ParallelReader:
        data_mode = "fixture"

        def read_evidence(self, principal, scope, arguments, deadline_monotonic):
            rendezvous.wait(timeout=2)
            return EvidenceRead(evidence_response(), True)

    subject = ToolGateway(
        Principal("review-user", "owner", Role.ANALYST),
        uuid4(),
        limits(max_concurrent_calls=2, max_total_output_bytes=8192),
        evidence_reader=ParallelReader(),
    )
    first_goal, second_goal = uuid4(), uuid4()
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [
            workers.submit(subject.execute, AgentRole.ASSESSOR, evidence_call(goal_id=goal))
            for goal in (first_goal, second_goal)
        ]
        first, second = [future.result(timeout=3) for future in futures]
    assert first.status == second.status == "succeeded"
    assert first.call_key != second.call_key and first.tool_run_id != second.tool_run_id
    assert {result.searched_scope.goal_id for result in subject.runs} == {first_goal, second_goal}
    assert sum(result.usage.result_bytes for result in subject.runs) <= 8192
    with pytest.raises(ValidationError):
        first.usage.result_bytes = 0
    with pytest.raises(ValidationError):
        first.data.quote_text = "altered by another caller"


def test_review_total_output_stop_is_terminal_and_does_not_reset_on_new_role() -> None:
    subject = gateway(max_result_bytes=1024, max_total_output_bytes=1024)
    first = subject.execute(AgentRole.CRITIC, comparison_call())
    assert first.status == "succeeded"
    with pytest.raises(GatewayStoppedError, match="output_budget_exhausted"):
        subject.execute(AgentRole.ASSESSOR, comparison_call())
    with pytest.raises(GatewayStoppedError, match="output_budget_exhausted"):
        subject.execute(AgentRole.CRITIC, comparison_call())
