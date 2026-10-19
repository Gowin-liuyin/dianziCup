"""Offline synthetic review probes; no network, credentials or production storage."""

import copy
import hashlib
import json
from uuid import UUID

import pytest
from pydantic import HttpUrl, SecretStr

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.contracts import EnrichmentBlock, EnrichmentContext, EnrichmentDocument
from ai_intel.enrichment.field_sources import FieldEvidenceError
from ai_intel.enrichment.model_fields import generate_model_field_attempts
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.network import FetchResult

RANGE = "PyPI demo affected versions: >=1.0,<2.0"
MECHANISM = "Untrusted text reaches an assistant."
PREREQUISITE = "Attacker can write documents."
PAPER = "Review Paper https://example.invalid/ref Analysis of demo incident."
POC = "Review PoC https://example.invalid/poc proof of concept; never executed."
TAXONOMY_URI = "https://raw.githubusercontent.com/mitre/atlas-data/" + "a" * 40 + "/dist/ATLAS.yaml"


def make_document(number, text, uri, kind="advisory", category="vendor_advisory", **fields):
    return EnrichmentDocument(
        revision_id=UUID(int=number),
        document_id=UUID(int=number + 100),
        source_id=UUID(int=number + 200),
        document_kind=kind,
        source_category=category,
        canonical_uri=uri,
        source_record_id=f"independent-synthetic-{number}",
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        blocks=(EnrichmentBlock(block_id=UUID(int=number + 300), start_offset=777, text=text, text_sha256=hashlib.sha256(text.encode()).hexdigest()),),
        blocks_complete=True,
        content_coverage="full_text",
        **fields,
    )


def make_documents():
    event = make_document(11, "\n".join((RANGE, "Fix: install demo 2.0.", "Mitigation: disable tools.", MECHANISM, PREREQUISITE, PAPER, POC)), "https://example.invalid/advisory")
    taxonomy = make_document(12, "AML.T0051: Prompt Injection", TAXONOMY_URI, "standard", "technical_standard", source_version="a" * 40)
    paper = make_document(13, PAPER, "https://example.invalid/ref", "paper", "academic_paper")
    return event, taxonomy, paper


def quote(document, text):
    block = document.blocks[0]
    offset = block.text.index(text)
    return {"revision_id": str(document.revision_id), "block_id": str(block.block_id), "start_offset": offset, "end_offset": offset + len(text), "quote_text": text}


def proposals(documents):
    event, taxonomy, paper = documents
    return {
        "atlas": {"candidates": [{"value": {"technique_id": "AML.T0051", "taxonomy_version": taxonomy.source_version, "mechanism": MECHANISM, "prerequisites": [PREREQUISITE]}, "evidence": [quote(event, MECHANISM), quote(event, PREREQUISITE), quote(taxonomy, taxonomy.blocks[0].text)]}]},
        "versions": {"candidates": [{"value": {"package_key": "demo", "ecosystem": "PyPI", "scheme": "pep440", "raw_expression": RANGE, "intervals": [{"introduced": "1.0", "fixed": "2.0"}], "vendor_fix": "Fix: install demo 2.0.", "mitigations": ["Mitigation: disable tools."]}, "evidence": [quote(event, RANGE), quote(event, "Fix: install demo 2.0."), quote(event, "Mitigation: disable tools.")]}]},
        "literature": {"candidates": [{"value": {"uri": "https://example.invalid/ref", "title": "Review Paper", "reference_kind": "paper", "relation": "analysis", "support_summary": "Analysis of demo incident."}, "evidence": [quote(paper, PAPER)]}]},
        "poc": {"candidates": [{"value": {"uri": "https://example.invalid/poc", "title": "Review PoC", "artifact_kind": "poc"}, "evidence": [quote(event, POC)]}]},
    }


def run(monkeypatch, documents=None, outputs=None, provider="openai", **policy):
    documents = documents or make_documents()
    outputs = outputs or proposals(documents)
    calls = []
    model = "deepseek-flash" if provider.startswith("deepseek") else "independent-synthetic-model"
    client = GenerationClient(provider, model, SecretStr("independent-synthetic-token"), limits=GenerationLimits(max_calls=2, total_timeout_seconds=1.0))

    def post(url, body, *, protocol_headers, deadline):
        request = json.loads(body)
        content = request["messages"][0]["content"][0]["text"] if provider.endswith("anthropic") else request["messages"][1]["content"]
        dimension = json.loads(content)["question"].split()[1]
        calls.append({"dimension": dimension, "url": url, "request": request})
        payload = outputs[dimension]
        if type(payload) is int:
            return FetchResult(url, payload, "application/json", b"{}")
        raw = payload if type(payload) is str else json.dumps(payload)
        if provider.endswith("anthropic"):
            wire = {"id": "independent-synthetic-call", "type": "message", "role": "assistant", "model": model, "stop_reason": "end_turn", "content": [{"type": "text", "text": raw}], "usage": {"input_tokens": 20, "output_tokens": 1}}
        else:
            wire = {"id": "independent-synthetic-call", "object": "chat.completion", "model": model, "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": raw}}], "usage": {"prompt_tokens": 20, "completion_tokens": 1, "total_tokens": 21}}
        return FetchResult(url, 200, "application/json", json.dumps(wire).encode())

    monkeypatch.setattr(client._gateway, "post_json", post)
    context = EnrichmentContext(event_id=UUID(int=9001), expected_event_version=1, revision_ids=tuple(item.revision_id for item in documents), rule_version="independent-synthetic-1")
    options = {"budget_authorized": True, "content_is_private": False, "egress_granted": False, **policy}
    result = generate_model_field_attempts(context, documents, client, **options)
    return result, calls


@pytest.mark.parametrize("provider", ["openai", "anthropic", "deepseek_openai", "deepseek_anthropic"])
def test_four_providers_preserve_hypotheses_and_bounded_calls(monkeypatch, provider):
    result, calls = run(monkeypatch, provider=provider, total_output_token_budget=7)
    assert len(calls) == 4
    assert len(result.model_attempts) == 4
    assert all(item.fee == "unknown" for item in result.model_attempts)
    assert all(item.status == DimensionStatus.PENDING for item in result.attempts)
    assert all(item.candidates[0].origin == ClaimOrigin.MODEL_HYPOTHESIS for item in result.attempts)
    assert all((item["request"].get("max_tokens") or item["request"].get("max_completion_tokens")) == 1 for item in calls)
    assert result.attempts[2].candidates[0].value.target_document_id == UUID(int=113)
    assert result.attempts[2].candidates[0].value.target_revision_id == UUID(int=13)
    assert result.attempts[3].candidates[0].value.static_status == "candidate_found"


@pytest.mark.parametrize("policy,code", [({"budget_authorized": False}, "model_budget_not_authorized"), ({"content_is_private": True}, "model_egress_denied")])
def test_denied_requests_have_no_wire_calls(monkeypatch, policy, code):
    result, calls = run(monkeypatch, **policy)
    assert calls == []
    assert result.model_attempts == ()
    assert all(item.error_code == code for item in result.attempts)


@pytest.mark.parametrize("value", [3, 8193, True, 4.0])
def test_invalid_budget_has_no_wire_call(monkeypatch, value):
    with pytest.raises(FieldEvidenceError, match="field_call_policy_invalid"):
        run(monkeypatch, total_output_token_budget=value)


@pytest.mark.parametrize("failure", [401, 429, "not json", '{"candidates":[],"candidates":[]}'])
def test_failure_isolated_and_no_format_repair(monkeypatch, failure):
    documents = make_documents()
    outputs = proposals(documents)
    outputs["versions"] = failure
    result, calls = run(monkeypatch, documents, outputs)
    assert len(calls) == 4
    assert result.attempts[1].candidates == ()
    assert all(len(result.attempts[index].candidates) == 1 for index in (0, 2, 3))


@pytest.mark.parametrize("field,value", [("origin", "human_confirmed"), ("tenant_id", "foreign"), ("supports_claim", True), ("status", "supported")])
def test_privileged_proposal_fields_cannot_survive(monkeypatch, field, value):
    outputs = proposals(make_documents())
    outputs["poc"]["candidates"][0][field] = value
    result, calls = run(monkeypatch, outputs=outputs)
    assert len(calls) == 4
    assert result.attempts[3].error_code == "model_format_invalid"
    assert result.attempts[3].candidates == ()


@pytest.mark.parametrize("status", ["static_reviewed", "verification_failed", "lab_verified"])
def test_poc_cannot_self_claim_review_or_exploit_status(monkeypatch, status):
    outputs = proposals(make_documents())
    outputs["poc"]["candidates"][0]["value"]["static_status"] = status
    result, _ = run(monkeypatch, outputs=outputs)
    assert result.attempts[3].candidates == ()
    assert result.attempts[3].error_code == "model_format_invalid"


@pytest.mark.parametrize("mutation", ["prefix_uri", "cross_revision", "target_identity", "nonextractive_summary"])
def test_literature_binding_and_evidence_boundary(monkeypatch, mutation):
    outputs = proposals(make_documents())
    item = outputs["literature"]["candidates"][0]
    if mutation == "prefix_uri":
        item["value"]["uri"] += "-other"
    elif mutation == "cross_revision":
        item["evidence"][0]["revision_id"] = str(UUID(int=9999))
    elif mutation == "target_identity":
        item["value"]["target_document_id"] = str(UUID(int=9999))
        item["value"]["target_revision_id"] = str(UUID(int=9998))
    else:
        item["value"]["support_summary"] = "This text proves a different vulnerability."
    result, _ = run(monkeypatch, outputs=outputs)
    assert result.attempts[2].candidates == ()


@pytest.mark.parametrize("coverage", ["metadata_only", "excerpt", "unknown"])
def test_partial_text_cannot_claim_analysis(monkeypatch, coverage):
    documents = make_documents()
    paper = documents[2].model_copy(update={"content_coverage": coverage, "blocks_complete": False})
    result, _ = run(monkeypatch, (documents[0], documents[1], paper), proposals(documents))
    assert result.attempts[2].candidates == ()
    assert result.attempts[2].error_code == "literature_fulltext_required"


@pytest.mark.parametrize("ecosystem,scheme", [("git", "git"), ("unlisted", "unknown")])
def test_unsupported_ecosystems_remain_unsupported(monkeypatch, ecosystem, scheme):
    documents = make_documents()
    line = f"{ecosystem} demo affected versions: >=1.0,<2.0"
    changed = make_document(11, line, "https://example.invalid/advisory")
    outputs = proposals(documents)
    outputs["versions"] = {"candidates": [{"value": {"package_key": "demo", "ecosystem": ecosystem, "scheme": scheme, "raw_expression": line, "intervals": [{"fixed": "2.0"}]}, "evidence": [quote(changed, line)]}]}
    result, _ = run(monkeypatch, (changed, documents[1], documents[2]), outputs)
    assert result.attempts[1].candidates[0].value.comparison_support == "unsupported"


def test_bad_local_candidate_preserves_valid_sibling(monkeypatch):
    outputs = proposals(make_documents())
    bad = copy.deepcopy(outputs["versions"]["candidates"][0])
    bad["value"]["intervals"] = [{"fixed": "9.9"}]
    outputs["versions"]["candidates"].append(bad)
    result, _ = run(monkeypatch, outputs=outputs)
    assert len(result.attempts[1].candidates) == 1
    assert result.attempts[1].status == DimensionStatus.PENDING
    assert result.attempts[1].error_code == "version_boundary_not_supported"


@pytest.mark.parametrize("mutation", ["missing_version", "partial", "wrong_domain"])
def test_missing_taxonomy_prevents_atlas_wire_call(monkeypatch, mutation):
    documents = make_documents()
    changes = {"missing_version": {"source_version": None}, "partial": {"blocks_complete": False}, "wrong_domain": {"canonical_uri": HttpUrl("https://example.invalid/taxonomy")}}[mutation]
    taxonomy = documents[1].model_copy(update=changes)
    result, calls = run(monkeypatch, (documents[0], taxonomy, documents[2]), proposals(documents))
    assert [item["dimension"] for item in calls] == ["versions", "literature", "poc"]
    assert result.attempts[0].error_code == "atlas_taxonomy_missing"


@pytest.mark.parametrize("version,uri", [("main", "https://raw.githubusercontent.com/mitre/atlas-data/main/dist/ATLAS.yaml"), ("latest", "https://atlas.mitre.org/techniques/AML.T0051")])
def test_mutable_taxonomy_version_cannot_authorize_atlas_call(monkeypatch, version, uri):
    documents = make_documents()
    taxonomy = documents[1].model_copy(update={"source_version": version, "canonical_uri": HttpUrl(uri)})
    selected = (documents[0], taxonomy, documents[2])
    outputs = proposals(selected)
    result, calls = run(monkeypatch, selected, outputs)
    assert [item["dimension"] for item in calls] == ["versions", "literature", "poc"]
    assert result.attempts[0].error_code == "atlas_taxonomy_missing"


def test_version_candidate_must_keep_adjacent_necessary_condition(monkeypatch):
    documents = make_documents()
    text = RANGE + "\nOnly when remote tools are enabled."
    changed = make_document(11, text, "https://example.invalid/advisory")
    outputs = proposals(documents)
    outputs["versions"] = {"candidates": [{"value": {"package_key": "demo", "ecosystem": "PyPI", "scheme": "pep440", "raw_expression": RANGE, "intervals": [{"introduced": "1.0", "fixed": "2.0"}]}, "evidence": [quote(changed, RANGE)]}]}
    result, _ = run(monkeypatch, (changed, documents[1], documents[2]), outputs)
    assert result.attempts[1].candidates == ()
    assert result.attempts[1].error_code


def test_poc_status_cannot_be_misread_as_system_execution(monkeypatch):
    documents = make_documents()
    result, calls = run(monkeypatch, documents)
    candidate = result.attempts[3].candidates[0]
    assert candidate.value.static_status == "candidate_found"
    assert candidate.origin == ClaimOrigin.MODEL_HYPOTHESIS
    assert any("no repository fetched, executed, or verified" in text for text in candidate.limitations)
    assert all(item["url"] == "https://api.openai.com/v1/chat/completions" for item in calls)
