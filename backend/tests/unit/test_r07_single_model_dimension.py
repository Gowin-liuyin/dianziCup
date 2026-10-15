"""Offline synthetic transport fixtures exercise the real codec and network gateway."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import count

import pytest
from pydantic import SecretStr
from tests.unit.test_r07_model_fields import context, fixture_documents, fixture_outputs

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment import model_fields
from ai_intel.enrichment.field_sources import FieldEvidenceError
from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.network import NetworkRequestError, NetworkTimeoutError

DIMENSIONS = ("atlas", "versions", "literature", "poc")


@dataclass
class FixtureResponse:
    status_code: int
    body: bytes

    @property
    def headers(self) -> dict[str, str]:
        return {"content-type": "application/json"}

    def iter_bytes(self) -> Iterator[bytes]:
        yield self.body

    def close(self) -> None:
        pass


def prepared_transport(
    monkeypatch, *, outputs=None, provider="openai", failure=None, timeout_seconds=20.0
):
    """Replace only offline DNS and transport; keep GenerationClient and gateway real."""
    outputs = fixture_outputs(fixture_documents()) if outputs is None else outputs
    model = "deepseek-flash" if provider.startswith("deepseek") else "fixture-model"
    client = GenerationClient(
        provider,
        model,
        SecretStr("offline-synthetic-token"),
        limits=GenerationLimits(total_timeout_seconds=timeout_seconds, max_calls=2),
    )
    calls = []

    def transport(url, addresses, deadline, headers, *, method="GET", body=None):
        request = json.loads(body)
        anthropic = provider.endswith("anthropic")
        user = json.loads(
            request["messages"][0]["content"][0]["text"]
            if anthropic
            else request["messages"][1]["content"]
        )
        dimension = user["question"].split()[1]
        calls.append((dimension, request, deadline.remaining_seconds(), method, url))
        assert addresses == ("8.8.8.8",)
        if failure == "network":
            raise NetworkRequestError("offline fixture")
        if failure == "timeout":
            raise NetworkTimeoutError("offline fixture")
        if failure in (401, 429, 503, 302):
            return FixtureResponse(failure, b"{}")
        raw = "not json" if failure == "format" else json.dumps(outputs[dimension])
        if anthropic:
            wire = {
                "id": "offline-fixture-call",
                "type": "message",
                "role": "assistant",
                "model": model,
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": raw}],
                "usage": {"input_tokens": 20, "output_tokens": 1},
            }
        else:
            wire = {
                "id": "offline-fixture-call",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": raw},
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 1, "total_tokens": 21},
            }
        return FixtureResponse(200, json.dumps(wire).encode())

    monkeypatch.setattr(
        client._gateway, "_resolve_addresses", lambda hostname, deadline: ["8.8.8.8"]
    )
    monkeypatch.setattr(client._gateway._transport, "request", transport)
    return client, calls


def extract(client, dimension, documents=None, **changes):
    documents = fixture_documents() if documents is None else documents
    policy = {"budget_authorized": True, "content_is_private": False, "egress_granted": False}
    policy.update(changes)
    return model_fields.extract_model_dimension(
        context(documents or fixture_documents()), documents, client, dimension=dimension, **policy
    )


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_one_selected_dimension_defaults_to_one_call_and_1024_tokens(monkeypatch, dimension):
    client, calls = prepared_transport(monkeypatch)
    original_limits = client.limits
    result = extract(client, dimension)
    assert [attempt.dimension for attempt in result.attempts] == [dimension]
    assert result.attempts[0].status == DimensionStatus.PENDING
    assert result.attempts[0].error_code == "model_hypothesis_requires_review"
    assert all(
        candidate.origin == ClaimOrigin.MODEL_HYPOTHESIS
        for candidate in result.attempts[0].candidates
    )
    assert len(calls) == len(result.model_attempts) == 1
    assert calls[0][0] == dimension
    assert calls[0][1]["max_completion_tokens"] == 1024
    assert 0 < calls[0][2] <= 20
    assert calls[0][3:] == ("POST", "https://api.openai.com/v1/chat/completions")
    assert client.limits is original_limits


@pytest.mark.parametrize("budget", [1, 4, 8192])
def test_explicit_single_output_budget_is_not_divided_or_truncated(monkeypatch, budget):
    client, calls = prepared_transport(monkeypatch)
    result = extract(client, "versions", total_output_token_budget=budget)
    assert len(result.model_attempts) == len(calls) == 1
    assert calls[0][1]["max_completion_tokens"] == budget


@pytest.mark.parametrize(
    "dimension", ["", "cvss", "Versions", None, True, (), ("versions", "versions"), ["versions"]]
)
def test_invalid_or_multiple_dimensions_reject_before_egress(monkeypatch, dimension):
    client, calls = prepared_transport(monkeypatch)
    with pytest.raises(FieldEvidenceError, match="field_dimension_invalid"):
        extract(client, dimension)
    assert calls == []


@pytest.mark.parametrize("budget", [True, 0, -1, 8193, 100.0, None])
def test_invalid_single_budget_rejects_before_egress(monkeypatch, budget):
    client, calls = prepared_transport(monkeypatch)
    with pytest.raises(FieldEvidenceError, match="field_call_policy_invalid"):
        extract(client, "versions", total_output_token_budget=budget)
    assert calls == []


@pytest.mark.parametrize("timeout_seconds", [20.001, 60.0, 120.0])
def test_long_client_deadline_is_a_zero_call_configuration_error(monkeypatch, timeout_seconds):
    client, calls = prepared_transport(monkeypatch, timeout_seconds=timeout_seconds)
    original_limits = client.limits
    with pytest.raises(FieldEvidenceError, match="field_single_dimension_timeout_invalid"):
        extract(client, "versions")
    assert calls == []
    assert client.limits is original_limits
    assert client.limits.total_timeout_seconds == timeout_seconds


@pytest.mark.parametrize("dimension", DIMENSIONS)
@pytest.mark.parametrize("early_failure", ["budget", "unconfigured", "empty"])
def test_early_results_contain_only_the_selected_dimension(monkeypatch, dimension, early_failure):
    client, calls = prepared_transport(monkeypatch)
    selected_client = None if early_failure == "unconfigured" else client
    documents = () if early_failure == "empty" else fixture_documents()
    result = extract(
        selected_client, dimension, documents, budget_authorized=early_failure != "budget"
    )
    reason = {
        "budget": "model_budget_not_authorized",
        "unconfigured": "model_not_configured",
        "empty": "field_evidence_missing",
    }[early_failure]
    assert [attempt.dimension for attempt in result.attempts] == [dimension]
    assert result.attempts[0].error_code == reason
    assert result.attempts[0].candidates == ()
    assert result.model_attempts == ()
    assert calls == []


def test_missing_pinned_atlas_taxonomy_skips_only_selected_atlas(monkeypatch):
    documents = fixture_documents()
    floating = documents[1].model_copy(update={"source_version": "main"})
    documents = (documents[0], floating, documents[2])
    client, calls = prepared_transport(monkeypatch)
    atlas = extract(client, "atlas", documents)
    assert len(atlas.attempts) == 1
    assert atlas.attempts[0].error_code == "atlas_taxonomy_missing"
    assert atlas.model_attempts == ()
    assert calls == []
    versions = extract(client, "versions", documents)
    assert versions.attempts[0].candidates
    assert [call[0] for call in calls] == ["versions"]


def test_single_version_keeps_full_conditions_and_unknown_comparison(monkeypatch):
    client, _ = prepared_transport(monkeypatch)
    candidate = extract(client, "versions").attempts[0].candidates[0]
    assert candidate.value.raw_expression == (
        "PyPI widget affected versions: >=1.0,<2.0; only when remote tools enabled."
    )
    assert candidate.value.comparison_support == "unknown"
    assert candidate.evidence[0].quote_text == candidate.value.raw_expression
    assert candidate.origin == ClaimOrigin.MODEL_HYPOTHESIS


def test_legacy_entry_keeps_four_dimensions_and_total_default_budget(monkeypatch):
    documents = fixture_documents()
    client, calls = prepared_transport(monkeypatch, timeout_seconds=60.0)
    result = model_fields.generate_model_field_attempts(
        context(documents),
        documents,
        client,
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
    )
    assert [attempt.dimension for attempt in result.attempts] == list(DIMENSIONS)
    assert [call[0] for call in calls] == list(DIMENSIONS)
    assert sum(call[1]["max_completion_tokens"] for call in calls) == 4096
    assert len(result.model_attempts) == 4


def test_single_dimension_preserves_smaller_client_deadline(monkeypatch):
    client, calls = prepared_transport(monkeypatch, timeout_seconds=0.5)
    extract(client, "versions")
    assert 0 < calls[0][2] <= 0.5
    assert client.limits.total_timeout_seconds == 0.5


def test_expired_before_generation_slot_returns_only_selected_failure(monkeypatch):
    client, calls = prepared_transport(monkeypatch, timeout_seconds=1.0)
    readings = count()
    monkeypatch.setattr(
        generation.time, "monotonic", lambda: 100.0 if next(readings) < 3 else 103.0
    )
    result = extract(client, "poc")
    assert [attempt.dimension for attempt in result.attempts] == ["poc"]
    assert result.attempts[0].error_code == "model_network_timeout"
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.model_attempts == ()
    assert calls == []
    assert client._slots.acquire(blocking=False)
    client._slots.release()
