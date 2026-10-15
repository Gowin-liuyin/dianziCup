"""The real generation codec uses a synthetic offline transport, never live models."""

import hashlib
import json

import pytest
from tests.unit.test_r07_input_capabilities import long_document
from tests.unit.test_r07_model_fields import context, document
from tests.unit.test_r07_single_model_dimension import prepared_transport

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.model_fields import extract_model_dimension


def output_for(source, line, *, quoted_block=None):
    block = source.blocks[-1] if quoted_block is None else quoted_block
    return {
        "versions": {
            "candidates": [
                {
                    "value": {
                        "package_key": "widget",
                        "ecosystem": "PyPI",
                        "scheme": "pep440",
                        "raw_expression": line,
                        "intervals": [{"fixed": "2.0"}],
                    },
                    "evidence": [
                        {
                            "revision_id": str(source.revision_id),
                            "block_id": str(block.block_id),
                            "start_offset": 0,
                            "end_offset": len(line),
                            "quote_text": line,
                        }
                    ],
                }
            ]
        }
    }


def extract(source, client, **policy):
    return extract_model_dimension(
        context((source,)),
        (source,),
        client,
        dimension="versions",
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
        **policy,
    )


def test_long67_positive_exact_quote_retains_hypothesis_and_one_bounded_wire(monkeypatch):
    source = long_document()
    client, calls = prepared_transport(
        monkeypatch, outputs=output_for(source, source.blocks[-1].text)
    )
    result = extract(source, client)
    candidate = result.attempts[0].candidates[0]
    assert candidate.origin == ClaimOrigin.MODEL_HYPOTHESIS
    assert result.attempts[0].status == DimensionStatus.PENDING
    assert candidate.evidence[0].block_id == source.blocks[-1].block_id
    assert (
        candidate.evidence[0].quote_sha256
        == hashlib.sha256(source.blocks[-1].text.encode()).hexdigest()
    )
    assert any("selection is incomplete" in item for item in candidate.limitations)
    assert len(result.input_selections[0].omitted_block_ids) == 66
    assert len(calls) == len(result.model_attempts) == 1
    assert calls[0][1]["max_completion_tokens"] == 1024
    assert calls[0][2] <= 20
    assert result.model_attempts[0].fee == "unknown"
    request = json.loads(calls[0][1]["messages"][1]["content"])
    evidence = request["untrusted_evidence"]
    assert len(evidence) <= 50
    assert sum(len(text.encode()) for text in evidence) <= 65536
    assert result.model_attempts[0].prompt_version == "r07-model-fields-2"


@pytest.mark.parametrize(
    "line",
    [
        "PyPI widget not affected versions: >=1.0,<2.0.",
        "PyPI widget unknown if affected versions: >=1.0,<2.0.",
    ],
)
def test_long67_negative_and_unknown_are_not_affected_candidates(monkeypatch, line):
    source = long_document(relevant=line)
    client, calls = prepared_transport(monkeypatch, outputs=output_for(source, line))
    result = extract(source, client)
    assert len(calls) == 1
    assert result.attempts[0].candidates == ()
    assert result.attempts[0].error_code == "version_negative_or_unknown_range"


def test_long67_empty_response_remains_unknown_with_incomplete_coverage(monkeypatch):
    source = long_document()
    client, calls = prepared_transport(monkeypatch, outputs={"versions": {"candidates": []}})
    result = extract(source, client)
    assert result.attempts[0].status == DimensionStatus.PENDING
    assert result.attempts[0].error_code == "field_evidence_missing"
    assert result.input_selections[0].incomplete
    assert len(calls) == 1


def test_long67_omitted_but_real_quote_is_rejected(monkeypatch):
    source = long_document()
    outputs = output_for(source, source.blocks[0].text, quoted_block=source.blocks[0])
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract(source, client)
    assert result.attempts[0].candidates == ()
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.attempts[0].error_code == "field_identifier_not_in_evidence"
    assert len(calls) == 1


def test_omitted_long_block_condition_still_blocks_candidate_from_full_source(monkeypatch):
    line = "PyPI widget affected versions: >=1.0,<2.0;"
    source = document(
        30,
        "Unrelated" * 1900 + "\n" + line + "\nOnly when tools enabled.",
        "https://example.invalid/long-qualifier",
    )
    outputs = output_for(source, line, quoted_block=source.blocks[0])
    start = source.blocks[0].text.index(line)
    outputs["versions"]["candidates"][0]["evidence"][0].update(
        start_offset=start,
        end_offset=start + len(line),
    )
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract(source, client)
    assert len(calls) == 1
    assert result.input_selections[0].incomplete
    assert result.attempts[0].candidates == ()
    assert result.attempts[0].error_code == "version_expression_context_missing"
    assert result.attempts[0].status == DimensionStatus.BLOCKED


def test_legal_unseen_version_quote_is_blocked_with_exact_selection_code(monkeypatch):
    source = long_document()
    line = source.blocks[-1].text
    blocks = tuple(
        block.model_copy(
            update={
                "text": line,
                "text_sha256": hashlib.sha256(line.encode()).hexdigest(),
            }
        )
        for block in source.blocks
    )
    source = source.model_copy(update={"blocks": blocks})
    client, calls = prepared_transport(monkeypatch, outputs=output_for(source, line))
    result = extract(source, client)
    assert len(calls) == 1
    assert result.attempts[0].status == DimensionStatus.BLOCKED
    assert result.attempts[0].error_code == "field_evidence_outside_selection"
    assert result.attempts[0].candidates == ()


@pytest.mark.parametrize("mutation", ["identifier", "content", "format"])
def test_partial_selection_does_not_reclassify_bad_model_output_as_blocked(monkeypatch, mutation):
    source = long_document()
    outputs = output_for(source, source.blocks[-1].text)
    if mutation == "identifier":
        outputs["versions"]["candidates"][0]["evidence"][0]["block_id"] = (
            "00000000-0000-0000-0000-000000000999"
        )
    elif mutation == "content":
        outputs["versions"]["candidates"][0]["value"]["intervals"] = [{"fixed": "3.0"}]
    else:
        outputs["versions"]["status"] = "available"
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract(source, client)
    assert len(calls) == 1
    assert result.input_selections[0].incomplete
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.attempts[0].candidates == ()


def test_seen_required_context_is_a_bad_proposal_even_if_other_text_was_omitted(monkeypatch):
    line = "PyPI widget affected versions: >=1.0,<2.0;"
    source = document(
        31,
        "Unrelated" * 1900 + "\n" + line + "\nOnly when affected package tools enabled.",
        "https://example.invalid/seen-qualifier",
    )
    outputs = output_for(source, line, quoted_block=source.blocks[0])
    start = source.blocks[0].text.index(line)
    outputs["versions"]["candidates"][0]["evidence"][0].update(
        start_offset=start,
        end_offset=start + len(line),
    )
    client, calls = prepared_transport(monkeypatch, outputs=outputs)
    result = extract(source, client)
    assert len(calls) == 1
    assert result.input_selections[0].incomplete
    assert result.attempts[0].status == DimensionStatus.FAILED
    assert result.attempts[0].error_code == "version_expression_context_missing"
