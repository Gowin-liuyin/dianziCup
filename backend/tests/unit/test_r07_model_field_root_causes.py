"""Synthetic offline boundaries for fixed taxonomy identity and complete condition evidence."""

import copy
import json
from dataclasses import dataclass

import pytest
from pydantic import HttpUrl, SecretStr
from test_r07_model_fields import (
    TAXONOMY_COMMIT,
    context,
    document,
    execute,
    fixture_documents,
    fixture_outputs,
    quote,
)

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.model_fields import generate_model_field_attempts
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.network import NetworkRequestError, NetworkTimeoutError

PINNED_URI = f"https://raw.githubusercontent.com/mitre/atlas-data/{TAXONOMY_COMMIT}/dist/ATLAS.yaml"
RANGE = "PyPI widget affected versions: >=1.0,<2.0"
CONDITION = "Only when remote tools are enabled."


@pytest.mark.parametrize(
    "version,uri",
    [
        (None, PINNED_URI),
        ("main", PINNED_URI),
        ("latest", PINNED_URI),
        ("fixture-taxonomy-1", PINNED_URI),
        ("v1.0", PINNED_URI),
        ("b" * 40, PINNED_URI),
        (TAXONOMY_COMMIT, "https://atlas.mitre.org/techniques/AML.T0051"),
        (TAXONOMY_COMMIT, PINNED_URI.replace(TAXONOMY_COMMIT, "main")),
        (TAXONOMY_COMMIT, PINNED_URI.replace(TAXONOMY_COMMIT, TAXONOMY_COMMIT[:12])),
        (TAXONOMY_COMMIT, PINNED_URI.replace("https:", "http:")),
        (TAXONOMY_COMMIT, PINNED_URI.replace("raw.githubusercontent.com", "example.invalid")),
        (TAXONOMY_COMMIT, PINNED_URI.replace("/mitre/", "/other/")),
        (TAXONOMY_COMMIT, PINNED_URI.replace("/ATLAS.yaml", "/other.yaml")),
        (TAXONOMY_COMMIT, PINNED_URI + "?ref=main"),
        (TAXONOMY_COMMIT, PINNED_URI + "#latest"),
        (TAXONOMY_COMMIT, PINNED_URI.replace("https://", "https://user@")),
        (TAXONOMY_COMMIT, PINNED_URI.replace(".com/", ".com:8443/")),
    ],
)
def test_unproven_taxonomy_identity_never_calls_atlas(monkeypatch, version, uri):
    documents = fixture_documents()
    taxonomy = documents[1].model_copy(
        update={"source_version": version, "canonical_uri": HttpUrl(uri)}
    )
    result, calls = execute(monkeypatch, documents=(documents[0], taxonomy, documents[2]))
    assert [call[0] for call in calls] == ["versions", "literature", "poc"]
    assert result.attempts[0].error_code == "atlas_taxonomy_missing"
    assert result.attempts[0].candidates == ()
    assert all(result.attempts[index].candidates for index in (1, 2, 3))


@pytest.mark.parametrize(
    "uri",
    [PINNED_URI, f"https://github.com/mitre/atlas-data/blob/{TAXONOMY_COMMIT}/dist/ATLAS.yaml"],
)
def test_exact_official_commit_pair_keeps_pending_mapping(monkeypatch, uri):
    documents = fixture_documents()
    taxonomy = documents[1].model_copy(update={"canonical_uri": HttpUrl(uri)})
    result, calls = execute(monkeypatch, documents=(documents[0], taxonomy, documents[2]))
    assert len(calls) == 4
    assert result.attempts[0].status == DimensionStatus.PENDING
    candidate = result.attempts[0].candidates[0]
    assert candidate.value.taxonomy_version == TAXONOMY_COMMIT
    assert candidate.origin == ClaimOrigin.MODEL_HYPOTHESIS


def test_model_version_cannot_replace_loaded_commit_identity(monkeypatch):
    outputs = fixture_outputs(fixture_documents())
    outputs["atlas"]["candidates"][0]["value"]["taxonomy_version"] = "b" * 40
    result, calls = execute(monkeypatch, outputs)
    assert len(calls) == 4
    assert result.attempts[0].candidates == ()
    assert result.attempts[0].error_code == "atlas_taxonomy_version_invalid"


def version_proposal(source, expression, extra_quotes=(), limitations=()):
    return {
        "candidates": [
            {
                "value": {
                    "package_key": "widget",
                    "ecosystem": "PyPI",
                    "scheme": "pep440",
                    "raw_expression": expression,
                    "intervals": [{"introduced": "1.0", "fixed": "2.0"}],
                    "limitations": limitations,
                },
                "evidence": [
                    quote(source, expression),
                    *(quote(source, text) for text in extra_quotes),
                ],
            }
        ]
    }


@pytest.mark.parametrize(
    "source_text",
    [
        RANGE + "\n" + CONDITION,
        CONDITION + "\n" + RANGE,
        RANGE + "\r\n" + CONDITION,
        RANGE + "\nOnly when remote tools are\nenabled.",
        RANGE + "\nOnly\nwhen remote tools are enabled.",
        RANGE + "\nRequires remote tools.\nProvided that write access is enabled.",
        RANGE + "\nPrerequisite: remote tools are enabled.",
        RANGE + "\nIf remote tools are enabled.",
        RANGE + "\nUnless tools are read-only.",
        RANGE + "\n仅当远程工具启用时。",
    ],
)
def test_range_without_source_conditions_is_rejected(monkeypatch, source_text):
    documents = fixture_documents()
    source = document(1, source_text, "https://example.invalid/advisory")
    outputs = copy.deepcopy(fixture_outputs(documents))
    outputs["versions"] = version_proposal(source, RANGE)
    result, _ = execute(monkeypatch, outputs, (source, *documents[1:]))
    assert result.attempts[1].candidates == ()
    assert result.attempts[1].error_code == "version_expression_context_missing"


@pytest.mark.parametrize("condition_in_limitation", [False, True])
def test_separate_quote_or_warning_does_not_restore_raw_expression(
    monkeypatch, condition_in_limitation
):
    documents = fixture_documents()
    source = document(1, RANGE + "\n" + CONDITION, "https://example.invalid/advisory")
    outputs = fixture_outputs(documents)
    outputs["versions"] = version_proposal(
        source, RANGE, (CONDITION,), (CONDITION,) if condition_in_limitation else ()
    )
    result, _ = execute(monkeypatch, outputs, (source, *documents[1:]))
    assert result.attempts[1].candidates == ()
    assert result.attempts[1].error_code == "version_expression_context_missing"


@pytest.mark.parametrize(
    "expression",
    [
        RANGE + "\n" + CONDITION,
        CONDITION + "\n" + RANGE,
        RANGE + "\r\n" + CONDITION,
        RANGE + "\nOnly when remote tools are\nenabled.",
        RANGE + "\nOnly\nwhen remote tools are enabled.",
        RANGE + "\nRequires remote tools.\nProvided that write access is enabled.",
    ],
)
def test_complete_conditioned_expression_remains_unknown_hypothesis(monkeypatch, expression):
    documents = fixture_documents()
    source = document(1, expression, "https://example.invalid/advisory")
    outputs = fixture_outputs(documents)
    outputs["versions"] = version_proposal(source, expression)
    result, _ = execute(monkeypatch, outputs, (source, *documents[1:]))
    attempt = result.attempts[1]
    assert attempt.status == DimensionStatus.PENDING
    assert len(attempt.candidates) == 1
    candidate = attempt.candidates[0]
    assert candidate.value.raw_expression == expression
    assert candidate.evidence[0].quote_text == expression
    assert candidate.value.comparison_support == "unknown"
    assert candidate.origin == ClaimOrigin.MODEL_HYPOTHESIS


def test_blank_paragraph_separates_unrelated_condition(monkeypatch):
    documents = fixture_documents()
    source = document(
        1, RANGE + "\n\nOther package requires tools.", "https://example.invalid/advisory"
    )
    outputs = fixture_outputs(documents)
    outputs["versions"] = version_proposal(source, RANGE)
    result, _ = execute(monkeypatch, outputs, (source, *documents[1:]))
    assert result.attempts[1].candidates[0].value.comparison_support == "unknown"


def test_second_condition_cannot_be_cut_after_first_complete_condition(monkeypatch):
    documents = fixture_documents()
    expression = RANGE + "\n" + CONDITION
    source = document(
        1, expression + "\nRequires write access.", "https://example.invalid/advisory"
    )
    outputs = fixture_outputs(documents)
    outputs["versions"] = version_proposal(source, expression)
    result, _ = execute(monkeypatch, outputs, (source, *documents[1:]))
    assert result.attempts[1].candidates == ()
    assert result.attempts[1].error_code == "version_expression_context_missing"


@dataclass
class FixtureResponse:
    status_code: int
    body: bytes

    @property
    def headers(self):
        return {"content-type": "application/json"}

    def iter_bytes(self):
        yield self.body

    def close(self):
        pass


@pytest.mark.parametrize(
    "failure", ["success", "format", "server", "redirect", "network", "timeout"]
)
def test_real_generation_and_gateway_make_at_most_four_transport_calls(monkeypatch, failure):
    documents = fixture_documents()
    outputs = fixture_outputs(documents)
    client = GenerationClient(
        "openai",
        "fixture-model",
        SecretStr("offline-synthetic-token"),
        limits=GenerationLimits(max_calls=2),
    )
    calls = []

    def transport(url, addresses, deadline, headers, *, method="GET", body=None):
        request = json.loads(body)
        dimension = json.loads(request["messages"][1]["content"])["question"].split()[1]
        calls.append((dimension, method, url))
        assert method == "POST"
        if failure == "network":
            raise NetworkRequestError("offline fixture")
        if failure == "timeout":
            raise NetworkTimeoutError("offline fixture")
        if failure in {"server", "redirect"}:
            return FixtureResponse(503 if failure == "server" else 302, b"{}")
        content = "not json" if failure == "format" else json.dumps(outputs[dimension])
        wire = {
            "id": "offline-fixture-call",
            "object": "chat.completion",
            "model": "fixture-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 1, "total_tokens": 21},
        }
        return FixtureResponse(200, json.dumps(wire).encode())

    monkeypatch.setattr(
        client._gateway, "_resolve_addresses", lambda hostname, deadline: ["8.8.8.8"]
    )
    monkeypatch.setattr(client._gateway._transport, "request", transport)
    result = generate_model_field_attempts(
        context(documents),
        documents,
        client,
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
    )
    assert [item[0] for item in calls] == ["atlas", "versions", "literature", "poc"]
    assert len(result.model_attempts) == 4
    if failure == "success":
        assert all(item.candidates for item in result.attempts)
    else:
        assert all(not item.candidates for item in result.attempts)
