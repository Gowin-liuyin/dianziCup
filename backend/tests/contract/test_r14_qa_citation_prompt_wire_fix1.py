"""Actual GenerationClient HTTP wire is mocked explicitly; these contracts are not live."""

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from ai_intel.answering.contracts import GeneratedAnswer
from ai_intel.answering.grounding import (
    GENERATION_SYSTEM,
    GroundedAnswerFailure,
    validate_citations,
)
from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.network import FetchResult
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import InvestigationRequest, json_object
from ai_intel.investigation.workflow_service import _initial_state, _WorkflowRuntime
from ai_intel.workers.executor import JobExecutionContext

SOURCE = "Synthetic fixture: component status unknown; no fix version confirmed."


def fixture_runtime():
    event_id, evidence_id, revision_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    evidence = EvidenceResponse(
        span_id=evidence_id,
        revision_id=revision_id,
        block_id=None,
        start_offset=0,
        end_offset=len(SOURCE),
        quote_text=SOURCE,
        quote_sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),
        locator_kind="text",
        page_number=None,
        json_pointer=None,
        verified_at=now,
        source_uri="https://example.invalid/qa-citation-fixture",
        source_published_at=None,
        source_modified_at=None,
        first_observed_at=now,
        ingested_at=now,
        data_mode="fixture",
    )
    runtime = _WorkflowRuntime(
        SimpleNamespace(_model_config={"model_version": "deepseek-flash"}),
        None,
        JobExecutionContext(str(uuid4()), "qa-wire-fixture", 1, None),
    )
    runtime.request = InvestigationRequest(
        question="Only state what this synthetic fixture says.",
        event_id=event_id,
        evidence_refs=(),
    )
    state = _initial_state("b" * 64)
    state["evidence"] = [json_object(evidence)]
    return runtime, state


def test_existing_generation_client_wire_carries_new_prompt_and_shared_unique_citation(monkeypatch):
    runtime, state = fixture_runtime()
    request = runtime.generation_request(state, GENERATION_SYSTEM, AgentRole.QA)
    evidence = runtime.projections(state)[0]
    candidate = {
        "claims": [
            {
                "text": "component status unknown",
                "kind": "source_fact",
                "support_ids": [str(evidence.evidence_id)],
            },
            {
                "text": "no fix version confirmed",
                "kind": "source_fact",
                "support_ids": [str(evidence.evidence_id)],
            },
        ],
        "citations": [{"evidence_id": str(evidence.evidence_id), "quote": SOURCE}],
    }
    client = GenerationClient(
        "deepseek_openai",
        "deepseek-flash",
        SecretStr("synthetic-citation-contract-credential"),
        limits=GenerationLimits(max_calls=1, max_concurrent_requests=1),
    )
    calls = []

    def post(url, body, *, protocol_headers, deadline):
        wire = json.loads(body)
        calls.append(wire)
        payload = {
            "id": "synthetic-qa-one-citation",
            "object": "chat.completion",
            "model": "deepseek-flash",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(candidate)},
                }
            ],
        }
        return FetchResult(url, 200, "application/json", json.dumps(payload).encode())

    monkeypatch.setattr(client._gateway, "post_json", post)
    generated = client.generate(request, GeneratedAnswer)
    assert len(calls) == len(generated.attempts) == 1
    assert "全局集合" in calls[0]["messages"][0]["content"]
    assert "每个evidence_id在citations中只能出现一次" in calls[0]["messages"][0]["content"]
    assert json.loads(calls[0]["messages"][1]["content"])["untrusted_evidence"] == list(
        request.evidence_texts
    )
    assert calls[0]["max_tokens"] == 2048
    assert "tools" not in calls[0]
    assert generated.attempts[0].prompt_version == "r14-qa-2"
    assert generated.attempts[0].schema_version == "r14-qa-1"
    assert generated.format_repair_used is False
    assert len(generated.value.claims) == 2 and len(generated.value.citations) == 1
    assert validate_citations(generated.value, (evidence,)) == (evidence,)


def test_duplicate_citations_remain_invalid_after_existing_http_wire_decode(monkeypatch):
    runtime, state = fixture_runtime()
    request = runtime.generation_request(state, GENERATION_SYSTEM, AgentRole.QA)
    evidence = runtime.projections(state)[0]
    candidate = {
        "claims": [
            {
                "text": "component status unknown",
                "kind": "source_fact",
                "support_ids": [str(evidence.evidence_id)],
            }
        ],
        "citations": [
            {"evidence_id": str(evidence.evidence_id), "quote": SOURCE},
            {"evidence_id": str(evidence.evidence_id), "quote": "component status unknown"},
        ],
    }
    client = GenerationClient(
        "deepseek_openai",
        "deepseek-flash",
        SecretStr("synthetic-duplicate-contract-credential"),
        limits=GenerationLimits(max_calls=1, max_concurrent_requests=1),
    )
    calls = []

    def post(url, body, *, protocol_headers, deadline):
        calls.append(json.loads(body))
        payload = {
            "id": "synthetic-qa-duplicate",
            "object": "chat.completion",
            "model": "deepseek-flash",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(candidate)},
                }
            ],
        }
        return FetchResult(url, 200, "application/json", json.dumps(payload).encode())

    monkeypatch.setattr(client._gateway, "post_json", post)
    generated = client.generate(request, GeneratedAnswer)
    assert len(calls) == len(generated.attempts) == 1
    assert len(generated.value.citations) == 2
    with pytest.raises(GroundedAnswerFailure, match="answer_citation_duplicate"):
        validate_citations(generated.value, (evidence,))
