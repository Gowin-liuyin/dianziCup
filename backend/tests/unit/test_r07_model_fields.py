"""Explicit synthetic unit fixtures exercise actual generation codecs; never count as live."""

import copy
import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import SecretStr

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.contracts import EnrichmentBlock, EnrichmentContext, EnrichmentDocument
from ai_intel.enrichment.field_sources import FieldEvidenceError
from ai_intel.enrichment.model_fields import generate_model_field_attempts
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.network import FetchResult

NOW = datetime(2026, 10, 16, tzinfo=UTC)
VERSION_LINE = "PyPI widget affected versions: >=1.0,<2.0; only when remote tools enabled."
MECHANISM = "Untrusted instructions enter a model input."
PREREQUISITE = "Attacker can write retrieved documents."
LITERATURE_LINE = "Fixture Paper https://example.invalid/paper Background about prompt injection."
POC_LINE = "Fixture PoC https://example.invalid/poc proof of concept; not executed."
TAXONOMY_COMMIT = "a" * 40


def identity(number):
    return UUID(int=number)


def document(number, text, uri, kind="advisory", category="vendor_advisory", **changes):
    return EnrichmentDocument(
        revision_id=identity(number),
        document_id=identity(number + 100),
        source_id=identity(number + 200),
        document_kind=kind,
        source_category=category,
        canonical_uri=uri,
        source_record_id=f"unit-fixture-{number}",
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        blocks=(
            EnrichmentBlock(
                block_id=identity(number + 300),
                start_offset=99,
                text=text,
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            ),
        ),
        blocks_complete=True,
        content_coverage="full_text",
        observed_at=NOW,
        **changes,
    )


def fixture_documents():
    event = document(
        1,
        "\n".join(
            (
                VERSION_LINE,
                "Fixed in 2.0.",
                "Mitigation: disable remote tools.",
                MECHANISM,
                PREREQUISITE,
                LITERATURE_LINE,
                POC_LINE,
            )
        ),
        "https://example.invalid/advisory",
    )
    taxonomy = document(
        2,
        "AML.T0051: Fixture prompt injection technique.",
        f"https://raw.githubusercontent.com/mitre/atlas-data/{TAXONOMY_COMMIT}/dist/ATLAS.yaml",
        "standard",
        "technical_standard",
        source_version=TAXONOMY_COMMIT,
    )
    paper = document(3, LITERATURE_LINE, "https://example.invalid/paper", "paper", "academic_paper")
    return (event, taxonomy, paper)


def context(documents):
    return EnrichmentContext(
        event_id=identity(999),
        expected_event_version=1,
        revision_ids=tuple(item.revision_id for item in documents),
        rule_version="unit-fixture-1",
    )


def quote(document, text):
    block = document.blocks[0]
    offset = block.text.index(text)
    return {
        "revision_id": str(document.revision_id),
        "block_id": str(block.block_id),
        "start_offset": offset,
        "end_offset": offset + len(text),
        "quote_text": text,
    }


def fixture_outputs(documents):
    event, taxonomy, paper = documents
    return {
        "atlas": {
            "candidates": [
                {
                    "value": {
                        "technique_id": "AML.T0051",
                        "taxonomy_version": TAXONOMY_COMMIT,
                        "mechanism": MECHANISM,
                        "prerequisites": [PREREQUISITE],
                    },
                    "evidence": [
                        quote(event, MECHANISM),
                        quote(event, PREREQUISITE),
                        quote(taxonomy, taxonomy.blocks[0].text),
                    ],
                }
            ]
        },
        "versions": {
            "candidates": [
                {
                    "value": {
                        "package_key": "widget",
                        "ecosystem": "PyPI",
                        "scheme": "pep440",
                        "raw_expression": VERSION_LINE,
                        "intervals": [{"introduced": "1.0", "fixed": "2.0"}],
                        "vendor_fix": "Fixed in 2.0.",
                        "mitigations": ["Mitigation: disable remote tools."],
                    },
                    "evidence": [
                        quote(event, VERSION_LINE),
                        quote(event, "Fixed in 2.0."),
                        quote(event, "Mitigation: disable remote tools."),
                    ],
                }
            ]
        },
        "literature": {
            "candidates": [
                {
                    "value": {
                        "uri": "https://example.invalid/paper",
                        "title": "Fixture Paper",
                        "reference_kind": "paper",
                        "relation": "background",
                        "support_summary": "Background about prompt injection.",
                    },
                    "evidence": [quote(paper, LITERATURE_LINE)],
                }
            ]
        },
        "poc": {
            "candidates": [
                {
                    "value": {
                        "uri": "https://example.invalid/poc",
                        "title": "Fixture PoC",
                        "artifact_kind": "poc",
                    },
                    "evidence": [quote(event, POC_LINE)],
                }
            ]
        },
    }


def prepared(monkeypatch, outputs, provider="openai", **limit_changes):
    client = GenerationClient(
        provider,
        "fixture-model",
        SecretStr("unit-fixture-credential"),
        limits=GenerationLimits(**limit_changes),
    )
    calls = []

    def post(url, body, *, protocol_headers, deadline):
        request = json.loads(body)
        if provider == "anthropic":
            user = json.loads(request["messages"][0]["content"][0]["text"])
        else:
            user = json.loads(request["messages"][1]["content"])
        dimension = user["question"].split()[1]
        calls.append((dimension, request, protocol_headers))
        payload = outputs[dimension]
        if isinstance(payload, int):
            return FetchResult(url, payload, "application/json", b"{}")
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        if provider == "anthropic":
            wire = {
                "id": "unit-fixture-call",
                "type": "message",
                "role": "assistant",
                "model": "fixture-model",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": raw}],
                "usage": {"input_tokens": 20, "output_tokens": 10},
            }
        else:
            wire = {
                "id": "unit-fixture-call",
                "object": "chat.completion",
                "model": "fixture-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": raw,
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            }
        return FetchResult(url, 200, "application/json", json.dumps(wire).encode())

    monkeypatch.setattr(client._gateway, "post_json", post)
    return client, calls


def execute(monkeypatch, outputs=None, documents=None, **changes):
    documents = documents or fixture_documents()
    client, calls = prepared(monkeypatch, outputs or fixture_outputs(documents))
    result = generate_model_field_attempts(
        context(documents),
        documents,
        client,
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
        **changes,
    )
    return result, calls


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_four_real_codecs_return_grounded_hypotheses(monkeypatch, provider):
    documents = fixture_documents()
    client, calls = prepared(monkeypatch, fixture_outputs(documents), provider)
    result = generate_model_field_attempts(
        context(documents),
        documents,
        client,
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
        total_output_token_budget=1000,
    )
    assert [attempt.dimension for attempt in result.attempts] == [
        "atlas",
        "versions",
        "literature",
        "poc",
    ]
    assert len(calls) == 4
    assert all(attempt.status == DimensionStatus.PENDING for attempt in result.attempts)
    assert all(len(attempt.candidates) == 1 for attempt in result.attempts)
    assert all(
        attempt.candidates[0].origin == ClaimOrigin.MODEL_HYPOTHESIS for attempt in result.attempts
    )
    versions = result.attempts[1].candidates[0].value
    assert versions.raw_expression == VERSION_LINE
    assert versions.vendor_fix == "Fixed in 2.0."
    assert versions.mitigations == ("Mitigation: disable remote tools.",)
    assert versions.comparison_support == "unknown"
    literature = result.attempts[2].candidates[0].value
    assert literature.target_document_id == documents[2].document_id
    assert literature.target_revision_id == documents[2].revision_id
    assert result.attempts[3].candidates[0].value.static_status == "candidate_found"
    evidence = result.attempts[1].candidates[0].evidence[0]
    assert evidence.start_offset == 0
    assert evidence.end_offset == len(VERSION_LINE)
    assert len(result.model_attempts) == 4
    assert all(metadata.fee == "unknown" for metadata in result.model_attempts)
    assert all(metadata.usage.output_tokens == 10 for metadata in result.model_attempts)
    assert all(
        (call[1].get("max_tokens") or call[1]["max_completion_tokens"]) == 250 for call in calls
    )


def test_no_source_and_unconfigured_are_distinct(monkeypatch):
    documents = fixture_documents()
    missing = generate_model_field_attempts(
        context(documents),
        documents,
        None,
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
    )
    assert all(attempt.error_code == "model_not_configured" for attempt in missing.attempts)
    client, calls = prepared(monkeypatch, fixture_outputs(documents))
    empty = generate_model_field_attempts(
        context(documents),
        (),
        client,
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
    )
    assert calls == []
    assert all(attempt.status == DimensionStatus.PENDING for attempt in empty.attempts)


def test_taxonomy_missing_does_not_call_atlas_or_invent_version(monkeypatch):
    documents = fixture_documents()
    outputs = fixture_outputs(documents)
    selected = (documents[0], documents[2])
    result, calls = execute(monkeypatch, outputs, selected)
    assert result.attempts[0].error_code == "atlas_taxonomy_missing"
    assert [call[0] for call in calls] == ["versions", "literature", "poc"]


@pytest.mark.parametrize("dimension", ["atlas", "versions", "literature", "poc"])
def test_missing_fields_remain_unknown_without_negative_search_claim(monkeypatch, dimension):
    outputs = fixture_outputs(fixture_documents())
    outputs[dimension] = {"candidates": []}
    result, _ = execute(monkeypatch, outputs)
    attempt = next(item for item in result.attempts if item.dimension == dimension)
    assert attempt.status == DimensionStatus.PENDING
    assert attempt.candidates == ()
    assert attempt.error_code == "field_evidence_missing"


@pytest.mark.parametrize(
    "payload",
    [
        "not JSON",
        '{"candidates":[],"candidates":[]}',
        {"candidates": [], "tenant_id": "invented"},
        401,
        429,
    ],
)
def test_one_failed_dimension_preserves_other_hypotheses_and_does_not_retry(monkeypatch, payload):
    outputs = fixture_outputs(fixture_documents())
    outputs["versions"] = payload
    result, calls = execute(monkeypatch, outputs)
    assert result.attempts[1].status in {DimensionStatus.FAILED, DimensionStatus.BLOCKED}
    assert result.attempts[1].candidates == ()
    assert all(len(result.attempts[index].candidates) == 1 for index in (0, 2, 3))
    assert len(calls) == 4


@pytest.mark.parametrize(
    "dimension,field,value",
    [
        ("atlas", "taxonomy_version", "invented"),
        ("atlas", "technique_id", "AML.T9999"),
        ("atlas", "mechanism", "Unrelated output becomes verified."),
        ("atlas", "prerequisites", ["Public input without permissions."]),
        ("versions", "intervals", [{"fixed": "3.0"}]),
        ("versions", "raw_expression", "affected versions <2.0"),
        ("versions", "vendor_fix", "Mitigation: disable remote tools."),
        ("versions", "mitigations", ["Fixed in 2.0."]),
        ("versions", "comparison_support", "supported"),
        ("literature", "title", "Other Paper"),
        ("literature", "uri", "https://example.invalid/other"),
        ("literature", "support_summary", "Verified vulnerability."),
        ("literature", "target_revision_id", str(identity(888))),
        ("poc", "static_status", "static_reviewed"),
        ("poc", "static_status", "lab_verified"),
        ("poc", "uri", "https://example.invalid/poc-extension"),
        ("poc", "commit_sha", "a" * 40),
        ("poc", "license_identifier", "MIT"),
        ("versions", "limitations", ["Confirmed safe in all deployments."]),
        ("literature", "limitations", ["The system verified all experimental results."]),
        ("poc", "limitations", ["Execution succeeded."]),
    ],
)
def test_fields_not_supported_by_source_are_rejected(monkeypatch, dimension, field, value):
    outputs = fixture_outputs(fixture_documents())
    outputs[dimension]["candidates"][0]["value"][field] = value
    result, _ = execute(monkeypatch, outputs)
    attempt = next(item for item in result.attempts if item.dimension == dimension)
    assert attempt.status == DimensionStatus.FAILED
    assert attempt.candidates == ()
    assert attempt.error_code


@pytest.mark.parametrize("mutation", ["revision", "block", "offset", "truncated", "duplicate"])
def test_exact_quote_cannot_escape_revision_block_or_context(monkeypatch, mutation):
    outputs = fixture_outputs(fixture_documents())
    item = outputs["versions"]["candidates"][0]
    if mutation == "revision":
        item["evidence"][0]["revision_id"] = str(identity(888))
    elif mutation == "block":
        item["evidence"][0]["block_id"] = str(identity(888))
    elif mutation == "offset":
        item["evidence"][0]["start_offset"] += 1
        item["evidence"][0]["end_offset"] += 1
    elif mutation == "truncated":
        item["evidence"][0] = {
            **item["evidence"][0],
            "start_offset": 5,
            "quote_text": VERSION_LINE[5:],
        }
        item["value"]["raw_expression"] = VERSION_LINE[5:]
    else:
        item["evidence"].append(copy.deepcopy(item["evidence"][0]))
    result, _ = execute(monkeypatch, outputs)
    assert result.attempts[1].status == DimensionStatus.FAILED
    assert result.attempts[1].candidates == ()


def test_competing_ranges_are_preserved_as_unverified_candidates(monkeypatch):
    documents = fixture_documents()
    second_line = "PyPI widget affected versions: >=1.0,<3.0; only when remote tools enabled."
    second_doc = document(4, second_line, "https://example.invalid/other-advisory")
    outputs = fixture_outputs(documents)
    second = {
        "value": {
            "package_key": "widget",
            "ecosystem": "PyPI",
            "scheme": "pep440",
            "raw_expression": second_line,
            "intervals": [{"fixed": "3.0"}],
        },
        "evidence": [quote(second_doc, second_line)],
    }
    outputs["versions"]["candidates"].append(second)
    outputs["versions"]["candidates"].append(copy.deepcopy(second))
    result, _ = execute(monkeypatch, outputs, (*documents, second_doc))
    assert result.attempts[1].status == DimensionStatus.PENDING
    assert len(result.attempts[1].candidates) == 2
    assert [candidate.value.intervals[0].fixed for candidate in result.attempts[1].candidates] == [
        "2.0",
        "3.0",
    ]


@pytest.mark.parametrize("scheme,ecosystem", [("git", "git"), ("unknown", "unlisted")])
def test_uncomparable_schemes_remain_explicitly_unsupported(monkeypatch, scheme, ecosystem):
    documents = fixture_documents()
    line = f"{ecosystem} widget affected versions: >=1.0,<2.0; only when remote tools enabled."
    changed = document(1, line, "https://example.invalid/advisory")
    selected = (changed, documents[1], documents[2])
    outputs = fixture_outputs(documents)
    outputs["versions"] = {
        "candidates": [
            {
                "value": {
                    "package_key": "widget",
                    "ecosystem": ecosystem,
                    "scheme": scheme,
                    "raw_expression": line,
                    "intervals": [{"fixed": "2.0"}],
                },
                "evidence": [quote(changed, line)],
            }
        ]
    }
    result, _ = execute(monkeypatch, outputs, selected)
    assert result.attempts[1].candidates[0].value.comparison_support == "unsupported"


@pytest.mark.parametrize("coverage", ["metadata_only", "excerpt", "unknown"])
def test_metadata_and_excerpts_never_become_fulltext_analysis(monkeypatch, coverage):
    documents = fixture_documents()
    paper = documents[2].model_copy(update={"content_coverage": coverage, "blocks_complete": False})
    outputs = fixture_outputs(documents)
    result, _ = execute(monkeypatch, outputs, (documents[0], documents[1], paper))
    assert "not full text" in result.attempts[2].candidates[0].limitations[1]
    outputs["literature"]["candidates"][0]["value"]["relation"] = "analysis"
    result, _ = execute(monkeypatch, outputs, (documents[0], documents[1], paper))
    assert result.attempts[2].error_code == "literature_fulltext_required"


@pytest.mark.parametrize("prefix", ["not affected", "unknown if affected"])
def test_negative_and_unknown_version_text_cannot_create_affected_range(monkeypatch, prefix):
    documents = fixture_documents()
    line = f"PyPI widget {prefix} versions: >=1.0,<2.0; only when remote tools enabled."
    changed = document(1, line, "https://example.invalid/advisory")
    outputs = fixture_outputs(documents)
    outputs["versions"] = {
        "candidates": [
            {
                "value": {
                    "package_key": "widget",
                    "ecosystem": "PyPI",
                    "scheme": "pep440",
                    "raw_expression": line,
                    "intervals": [{"fixed": "2.0"}],
                },
                "evidence": [quote(changed, line)],
            }
        ]
    }
    result, _ = execute(monkeypatch, outputs, (changed, documents[1], documents[2]))
    assert result.attempts[1].error_code == "version_negative_or_unknown_range"


def test_context_cannot_include_unselected_revision(monkeypatch):
    documents = fixture_documents()
    client, calls = prepared(monkeypatch, fixture_outputs(documents))
    selected_context = context((documents[0],))
    with pytest.raises(FieldEvidenceError, match="field_revision_outside_context"):
        generate_model_field_attempts(
            selected_context,
            documents,
            client,
            budget_authorized=True,
            content_is_private=False,
            egress_granted=False,
        )
    assert calls == []


def test_explicit_source_prerequisite_cannot_be_dropped(monkeypatch):
    outputs = fixture_outputs(fixture_documents())
    outputs["atlas"]["candidates"][0]["value"]["prerequisites"] = []
    result, _ = execute(monkeypatch, outputs)
    assert result.attempts[0].error_code == "atlas_prerequisite_context_missing"


def test_local_failure_preserves_other_valid_candidates_in_same_dimension(monkeypatch):
    outputs = fixture_outputs(fixture_documents())
    invalid = copy.deepcopy(outputs["versions"]["candidates"][0])
    invalid["value"]["intervals"] = [{"fixed": "8.0"}]
    outputs["versions"]["candidates"].append(invalid)
    result, _ = execute(monkeypatch, outputs)
    assert result.attempts[1].status == DimensionStatus.PENDING
    assert len(result.attempts[1].candidates) == 1
    assert result.attempts[1].error_code == "version_boundary_not_supported"


def test_literature_binding_rejects_ambiguous_target_revisions(monkeypatch):
    documents = fixture_documents()
    older_paper = document(
        5, LITERATURE_LINE, "https://example.invalid/paper", "paper", "academic_paper"
    )
    result, _ = execute(monkeypatch, fixture_outputs(documents), (*documents, older_paper))
    assert result.attempts[2].error_code == "literature_target_revision_ambiguous"


def test_unloaded_literature_target_remains_unbound_link_candidate(monkeypatch):
    documents = fixture_documents()
    outputs = fixture_outputs(documents)
    outputs["literature"]["candidates"][0]["evidence"] = [quote(documents[0], LITERATURE_LINE)]
    result, _ = execute(monkeypatch, outputs, documents[:2])
    value = result.attempts[2].candidates[0].value
    assert value.target_document_id is None
    assert value.target_revision_id is None


def test_fixed_boundary_is_never_reinterpreted_as_explicit_affected_version(monkeypatch):
    outputs = fixture_outputs(fixture_documents())
    outputs["versions"]["candidates"][0]["value"]["explicit_versions"] = ["2.0"]
    result, _ = execute(monkeypatch, outputs)
    assert result.attempts[1].error_code == "version_explicit_not_supported"


def test_source_content_hash_and_block_hash_are_revalidated_before_call(monkeypatch):
    documents = fixture_documents()
    block = documents[0].blocks[0].model_copy(update={"text": "tampered"})
    tampered = documents[0].model_copy(update={"blocks": (block,)})
    client, calls = prepared(monkeypatch, fixture_outputs(documents))
    with pytest.raises(FieldEvidenceError, match="field_documents_invalid"):
        generate_model_field_attempts(
            context(documents),
            (tampered, *documents[1:]),
            client,
            budget_authorized=True,
            content_is_private=False,
            egress_granted=False,
        )
    assert calls == []


def test_oversized_input_is_rejected_without_silent_truncation(monkeypatch):
    documents = fixture_documents()
    oversized = document(1, "x" * 18000, "https://example.invalid/advisory")
    client, calls = prepared(monkeypatch, fixture_outputs(documents))
    with pytest.raises(FieldEvidenceError, match="field_input_budget_exhausted"):
        generate_model_field_attempts(
            context(documents),
            (oversized, *documents[1:]),
            client,
            budget_authorized=True,
            content_is_private=False,
            egress_granted=False,
        )
    assert calls == []


def test_partial_taxonomy_cannot_supply_mapping_authority(monkeypatch):
    documents = fixture_documents()
    taxonomy = documents[1].model_copy(update={"blocks_complete": False})
    result, calls = execute(
        monkeypatch, fixture_outputs(documents), (documents[0], taxonomy, documents[2])
    )
    assert result.attempts[0].error_code == "atlas_taxonomy_missing"
    assert len(calls) == 3
