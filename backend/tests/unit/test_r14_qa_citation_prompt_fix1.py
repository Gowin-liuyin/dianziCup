"""QA prompt contracts use saved public results and pure fixture state, never service IO."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.answering.contracts import GeneratedAnswer
from ai_intel.answering.grounding import (
    GENERATION_SYSTEM,
    VERIFICATION_SYSTEM,
    GroundedAnswerFailure,
    validate_citations,
)
from ai_intel.api.knowledge_contracts import CitationProjection, EvidenceResponse
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import InvestigationRequest, json_object
from ai_intel.investigation.workflow_service import _initial_state, _WorkflowRuntime
from ai_intel.workers.executor import JobExecutionContext

ROOT = Path(__file__).resolve().parents[3]
SAVED_RESULT = (
    ROOT / "reports/runs/recovery_r14_qa_citation_prompt_fix1_20261016/old_trial_probe_result.json"
)
SAVED_SHA256 = "769b0684ce0a1b9b6ca01adc386d2098154ffcdf8d0cd9fe6073cc8985f6aa5d"


def saved_runtime():
    raw = SAVED_RESULT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SAVED_SHA256
    saved = json.loads(raw)
    response = EvidenceResponse.model_validate_json(json.dumps(saved["initial_reader"]["data"]))
    runtime = _WorkflowRuntime(
        SimpleNamespace(_model_config={"model_version": "deepseek-flash"}),
        None,
        JobExecutionContext(str(uuid4()), "qa-prompt-fixture", 1, None),
    )
    runtime.request = InvestigationRequest.model_validate_json(json.dumps(saved["request"]))
    state = _initial_state("a" * 64)
    state["evidence"] = [json_object(response)]
    return runtime, state, saved


def test_qa_request_explains_global_unique_citations_and_claim_reuse():
    runtime, state, _ = saved_runtime()
    request = runtime.generation_request(state, GENERATION_SYSTEM, AgentRole.QA)
    assert request.system_text.startswith(GENERATION_SYSTEM)
    assert "全局集合" in request.system_text
    assert "每个evidence_id在citations中只能出现一次" in request.system_text
    assert "多个claims.support_ids可引用同一条citation" in request.system_text
    assert "连续、精确、单行原文子串" in request.system_text
    assert "不得把不相邻片段拼接成quote" in request.system_text
    assert "不得制造或改写UUID、revision_id、版本和offset" in request.system_text
    assert "未知、否定、条件和冲突必须保留" in request.system_text


def test_only_qa_prompt_version_changes_without_schema_or_budget_changes():
    runtime, state, _ = saved_runtime()
    request = runtime.generation_request(state, GENERATION_SYSTEM, AgentRole.QA)
    assert request.prompt_version == "r14-qa-2"
    assert request.schema_version == "r14-qa-1"
    assert request.max_output_tokens == 2048
    assert request.allow_format_repair is False
    assert request.model_version == "deepseek-flash"


@pytest.mark.parametrize("role", [AgentRole.ORCHESTRATOR, AgentRole.CRITIC])
def test_non_qa_prompt_and_version_are_unchanged(role):
    runtime, state, _ = saved_runtime()
    system = VERIFICATION_SYSTEM if role == AgentRole.CRITIC else "fixture planner instruction"
    request = runtime.generation_request(state, system, role)
    assert request.system_text == system
    assert request.prompt_version == request.schema_version == "r14-" + role.value + "-1"


def test_evidence_uuid_revision_locator_and_quote_are_transmitted_unchanged():
    runtime, state, _ = saved_runtime()
    before = json.dumps(state, sort_keys=True)
    projected = runtime.projections(state)
    request = runtime.generation_request(state, GENERATION_SYSTEM, AgentRole.QA)
    assert request.evidence_texts == tuple(item.model_dump_json() for item in projected)
    assert json.dumps(state, sort_keys=True) == before
    assert str(projected[0].evidence_id) in request.evidence_texts[0]
    assert str(projected[0].revision_id) in request.evidence_texts[0]
    assert projected[0].locator == "json_pointer:253:1179"


def test_old_real_candidate_is_still_rejected_as_duplicate_without_repair():
    runtime, state, saved = saved_runtime()
    operation = next(item for item in saved["operations"] if item["operation_key"] == "model:qa")
    candidate = GeneratedAnswer.model_validate_json(json.dumps(operation["output_json"]["value"]))
    assert len(candidate.claims) == 8 and len(candidate.citations) == 6
    assert len({item.evidence_id for item in candidate.citations}) == 1
    assert all(item.quote in runtime.projections(state)[0].quote for item in candidate.citations)
    with pytest.raises(GroundedAnswerFailure, match="answer_citation_duplicate"):
        validate_citations(candidate, runtime.projections(state))
    assert hashlib.sha256(SAVED_RESULT.read_bytes()).hexdigest() == SAVED_SHA256


def test_cross_document_quote_cannot_be_attached_to_another_authorized_evidence_id():
    runtime, state, _ = saved_runtime()
    original = runtime.projections(state)[0]
    unrelated = CitationProjection(
        evidence_id=uuid4(),
        revision_id=uuid4(),
        quote="Synthetic unrelated document: exploit observation is unknown.",
        locator="text:0:60",
        source_uri="https://example.invalid/other-document-fixture",
    )
    candidate = GeneratedAnswer.model_validate_json(
        json.dumps(
            {
                "claims": [
                    {
                        "text": "exploit observation is unknown",
                        "kind": "source_fact",
                        "support_ids": [str(original.evidence_id)],
                    }
                ],
                "citations": [{"evidence_id": str(original.evidence_id), "quote": unrelated.quote}],
            }
        )
    )
    with pytest.raises(GroundedAnswerFailure, match="answer_citation_invalid"):
        validate_citations(candidate, (original, unrelated))


def test_missing_global_citation_cannot_support_a_fact():
    runtime, state, _ = saved_runtime()
    original = runtime.projections(state)[0]
    candidate = GeneratedAnswer.model_validate_json(
        json.dumps(
            {
                "claims": [
                    {
                        "text": "fixture fact",
                        "kind": "source_fact",
                        "support_ids": [str(original.evidence_id)],
                    }
                ],
                "citations": [],
            }
        )
    )
    with pytest.raises(GroundedAnswerFailure, match="answer_support_invalid"):
        validate_citations(candidate, (original,))


@pytest.mark.parametrize("field", ["revision_id", "offset", "source_uri", "supported"])
def test_candidate_dto_still_rejects_model_supplied_metadata_or_support_verdict(field):
    _, _, saved = saved_runtime()
    identifier = saved["initial_reader"]["data"]["span_id"]
    payload = {
        "claims": [{"text": "fixture fact", "kind": "source_fact", "support_ids": [identifier]}],
        "citations": [{"evidence_id": identifier, "quote": "fixture quote", field: "forged"}],
    }
    with pytest.raises(ValidationError):
        GeneratedAnswer.model_validate_json(json.dumps(payload))
