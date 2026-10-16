"""Independent offline old-checkpoint recovery probes never invoke a real model or PG."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph import build_investigation_graph
from ai_intel.investigation.graph_contracts import RoleReceipt, json_object
from ai_intel.investigation.tool_contracts import CompareVersionsArguments, ReadEvidenceArguments
from ai_intel.investigation.workflow_service import _initial_state

__all__ = ["consumer_fixture"]

RUN = Path(__file__).parent


class OfflineModelBoundaryReached(RuntimeError):
    """An explicit sentinel records a model factory attempt without creating a client."""


def legacy_assessor_checkpoint(fixture):
    fixture.runtime.request = fixture.runtime.request.model_copy(
        update={
            "version_comparison": CompareVersionsArguments(
                left_version="1.0", right_version="2.0", scheme="pep440", ecosystem="pypi"
            )
        }
    )
    source = json.loads((RUN / "original_graph_unknown_samples.json").read_bytes())[1]
    receipts = source["role_receipts"][:6]
    receipts[-1] = json_object(
        RoleReceipt(
            role=AgentRole.ASSESSOR,
            status="partial",
            reason_code="assessment_adapter_not_configured",
            evidence_ids=(),
            operation_keys=("tool:compare_versions", "tool:assessor:get_inventory"),
            output=receipts[-1]["output"],
        )
    )
    reference = ReadEvidenceArguments(
        event_id=fixture.runtime.request.event_id, evidence_id=uuid4(), revision_id=uuid4()
    )
    fixture.runtime.request = fixture.runtime.request.model_copy(update={"evidence_refs": (reference,)})
    quote = "explicit isolated fixture support"
    evidence = EvidenceResponse(
        span_id=reference.evidence_id,
        revision_id=reference.revision_id,
        block_id=None,
        start_offset=0,
        end_offset=len(quote),
        quote_text=quote,
        quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
        locator_kind="text",
        page_number=None,
        json_pointer=None,
        verified_at=datetime(2026, 10, 16, tzinfo=UTC),
        source_uri="https://example.invalid/isolated-fixture",
        source_published_at=None,
        source_modified_at=None,
        first_observed_at=None,
        ingested_at=None,
        data_mode="fixture",
    )
    fixture.records["tool:compare_versions"] = {"error_code": "operation_outcome_unknown"}
    fixture.records["tool:assessor:get_inventory"] = {"confirmed_fixture_result": True}
    return {
        **_initial_state("a" * 64),
        "status": "partial",
        "stop_reason": "evidence_unavailable",
        "receipts": receipts,
        "evidence": [json_object(evidence)],
    }


def observe_next_role(fixture, state, invoke):
    model_attempts = []

    def model_factory(limits):
        model_attempts.append({"max_calls": limits.max_calls})
        raise OfflineModelBoundaryReached("explicit fixture model factory reached; no IO")

    fixture.runtime.service.model_factory = model_factory
    fixture.runtime.service._model_config = {"model_version": "isolated-fixture-model"}
    before = json.dumps(state, sort_keys=True)
    try:
        result = invoke()
        boundary_error = None
    except OfflineModelBoundaryReached as error:
        result = None
        boundary_error = str(error)
    sample = {
        "input_state": json.loads(before),
        "input_receipts_unchanged": json.dumps(state, sort_keys=True) == before,
        "operation_receipts": fixture.records,
        "new_reservations": fixture.reservations,
        "tool_names": [call.tool_name for _, call in fixture.calls],
        "model_factory_attempts": model_attempts,
        "model_io": 0,
        "result": result,
        "boundary_error": boundary_error,
    }
    return sample


@pytest.mark.parametrize("role", [AgentRole.QA, AgentRole.REPORTER])
def test_next_role_reads_hidden_unknown_before_any_new_reservation(consumer_fixture, role):
    fixture = consumer_fixture
    state = legacy_assessor_checkpoint(fixture)
    sample = observe_next_role(fixture, state, lambda: fixture.runtime.run_role(role, state))
    (RUN / ("incoming_direct_" + role.value + ".json")).write_text(
        json.dumps(sample, indent=2) + "\n", encoding="utf-8"
    )
    assert sample["new_reservations"] == []
    assert sample["tool_names"] == [] and sample["model_factory_attempts"] == []
    assert sample["result"]["status"] == "partial"
    assert sample["result"]["stop_reason"] == "operation_outcome_unknown"
    assert sample["input_receipts_unchanged"] is True


@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
def test_actual_checkpoint_resume_reads_hidden_unknown_before_qa(consumer_fixture, strategy):
    fixture = consumer_fixture
    fixture.runtime.request = fixture.runtime.request.model_copy(update={"strategy": strategy})
    state = legacy_assessor_checkpoint(fixture)
    graph = build_investigation_graph(strategy, fixture.runtime.run_role, InMemorySaver())
    config = {"configurable": {"thread_id": "isolated-fixture-checkpoint-" + strategy}}
    previous_node = "asset_agent" if strategy == "B2" else "assessor"
    graph.update_state(config, state, as_node=previous_node)
    pending = graph.get_state(config).next
    assert pending == (("answer_agent",) if strategy == "B2" else ("qa",))
    sample = observe_next_role(fixture, state, lambda: graph.invoke(None, config))
    sample["checkpoint_next_before_resume"] = pending
    (RUN / ("incoming_resume_" + strategy + ".json")).write_text(
        json.dumps(sample, indent=2) + "\n", encoding="utf-8"
    )
    assert sample["new_reservations"] == []
    assert sample["tool_names"] == [] and sample["model_factory_attempts"] == []
    assert sample["result"]["stop_reason"] == "operation_outcome_unknown"
    assert sample["input_receipts_unchanged"] is True
