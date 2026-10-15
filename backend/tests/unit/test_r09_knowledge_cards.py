"""R09候选卡单元边界；所有资料和模型响应均为显式fixture。"""

import hashlib
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.enrichment.card_extraction import (
    CardExtractionFailure,
    CardExtractionOutput,
    build_knowledge_card,
    extract_knowledge_card,
)
from ai_intel.enrichment.knowledge_cards import verification_label
from ai_intel.infrastructure.network import NetworkRequestError, NetworkTimeoutError
from r09_card_fixtures import PUBLIC_SCOPE, candidate_field, prepared_client, source_document


def output(fields: list[dict[str, object]]) -> CardExtractionOutput:
    return CardExtractionOutput.model_validate_json(json.dumps({"fields": fields}), strict=True)


def test_no_author_or_reproduction_is_unknown() -> None:
    assert verification_label(False, False) == "unknown"


def test_unicode_subquote_uses_saved_revision_offsets_and_hash() -> None:
    source = source_document()
    quote = "只有开启写文件工具的助手才可能修改文件。"
    draft = build_knowledge_card(source, output([candidate_field(source, quote=quote)]))
    field = next(item for item in draft.fields if item.field_name == "tool_permissions")
    citation = field.proposed_values[0].citations[0]
    assert field.status == "candidate" and field.semantic_support == "unverified"
    assert field.document_id == source.document.document_id
    assert citation.revision_id == source.document.revision_id and citation.revision_number == 1
    assert citation.block_id == source.evidence[0].block_id
    assert citation.quote_text == quote
    assert citation.start_offset == 11 and citation.end_offset == 31
    assert citation.quote_sha256 == hashlib.sha256(quote.encode()).hexdigest()
    assert draft.data_mode == "fixture" and draft.confirmation_status == "awaiting_review"


def test_absent_fields_are_unknown_without_fabricated_values_or_quotes() -> None:
    source = source_document()
    draft = build_knowledge_card(source, output([]))
    assert draft.fields
    assert all(field.status == "unknown" and field.proposed_values == () for field in draft.fields)
    assert all(field.revision_id == source.document.revision_id for field in draft.fields)
    assert draft.verification_level == "unknown"


def test_conflicting_values_remain_parallel_and_unconfirmed() -> None:
    source = source_document(("Writing permission is required.", "Read-only tools suffice."))
    fields = [
        candidate_field(source, value="write_tools"),
        candidate_field(source, value="read_only", evidence_index=1),
    ]
    draft = build_knowledge_card(source, output(fields))
    field = next(item for item in draft.fields if item.field_name == "tool_permissions")
    assert field.status == "conflict"
    assert [value.value for value in field.proposed_values] == ["write_tools", "read_only"]
    assert field.semantic_support == "unverified"


@pytest.mark.parametrize("duplicate", ["value", "citation"])
def test_duplicate_model_items_cannot_overwrite_or_inflate_support(duplicate: str) -> None:
    source = source_document()
    field = candidate_field(source)
    fields = [field, field] if duplicate == "value" else [field]
    if duplicate == "citation":
        field["citations"] = [field["citations"][0], field["citations"][0]]
    with pytest.raises(CardExtractionFailure, match="card_duplicate_" + duplicate):
        build_knowledge_card(source, output(fields))


@pytest.mark.parametrize("status", ["pending", "failed", "legacy_unverified"])
def test_unparsed_source_does_not_become_extracted_card(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    source = source_document()
    source = source.model_copy(
        update={"document": source.document.model_copy(update={"parse_status": status})}
    )
    client, calls = prepared_client(monkeypatch, {"fields": []})
    with pytest.raises(CardExtractionFailure, match="card_source_invalid"):
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert calls == []


@pytest.mark.parametrize(
    "change,code",
    [
        ({"evidence_id": str(uuid4())}, "card_evidence_unknown"),
        ({"quote": "invented source"}, "card_quote_invalid"),
        ({"start_offset": 999}, "card_quote_invalid"),
    ],
)
def test_candidate_cannot_invent_quote_identity_or_occurrence(
    change: dict[str, object], code: str
) -> None:
    source = source_document()
    with pytest.raises(CardExtractionFailure, match=code):
        build_knowledge_card(source, output([candidate_field(source, **change)]))


def test_repeated_quote_requires_exact_occurrence() -> None:
    source = source_document(("write. write.",))
    draft = build_knowledge_card(
        source, output([candidate_field(source, quote="write.", start_offset=7)])
    )
    field = next(item for item in draft.fields if item.field_name == "tool_permissions")
    assert field.proposed_values[0].citations[0].start_offset == 7


@pytest.mark.parametrize("coverage", ["abstract", "feed_excerpt", "metadata", "unknown"])
def test_incomplete_source_coverage_is_preserved(coverage: str) -> None:
    source = source_document()
    source = source.model_copy(
        update={"document": source.document.model_copy(update={"content_coverage": coverage})}
    )
    draft = build_knowledge_card(source, output([]))
    assert draft.content_coverage == coverage and "source_coverage_incomplete" in draft.limitations
    assert all(field.status == "unknown" for field in draft.fields)


def test_partial_parser_and_page_do_not_announce_full_text_absence() -> None:
    source = source_document(evidence_total=2, next_evidence_offset=1)
    source = source.model_copy(
        update={"document": source.document.model_copy(update={"parse_status": "partial"})}
    )
    draft = build_knowledge_card(source, output([]))
    assert "source_parse_partial" in draft.limitations
    assert "source_evidence_subset" in draft.limitations
    assert all(field.status != "not_found" for field in draft.fields)


@pytest.mark.parametrize(
    "change",
    [
        {"quote_sha256": "0" * 64},
        {"block_id": None},
        {"verified_at": None},
        {"locator_kind": "legacy_unverified"},
        {"end_offset": 999},
        {"revision_id": uuid4()},
        {"data_mode": "live"},
    ],
)
def test_tampered_or_legacy_source_rejected_before_client(
    monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    source = source_document()
    source = source.model_copy(update={"evidence": (source.evidence[0].model_copy(update=change),)})
    client, calls = prepared_client(monkeypatch, {"fields": []})
    with pytest.raises(CardExtractionFailure, match="card_source_invalid"):
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert calls == []


def test_empty_evidence_rejected_without_successful_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, calls = prepared_client(monkeypatch, {"fields": []})
    with pytest.raises(CardExtractionFailure, match="card_evidence_missing"):
        extract_knowledge_card(client, source_document(texts=()), PUBLIC_SCOPE)
    assert calls == []


@pytest.mark.parametrize(
    "response,code",
    [
        (401, "model_permanent_auth_error"),
        (429, "model_rate_limited"),
        (NetworkTimeoutError("synthetic"), "model_network_timeout"),
        (NetworkRequestError("synthetic"), "model_network_failure"),
        ("invalid-json", "model_format_invalid"),
        ({"fields": [], "confirmed": True}, "model_format_invalid"),
    ],
)
def test_model_failure_is_explicit_with_real_attempt_and_no_fallback(
    monkeypatch: pytest.MonkeyPatch, response: object, code: str
) -> None:
    client, calls = prepared_client(monkeypatch, response)
    with pytest.raises(CardExtractionFailure, match=code) as failure:
        extract_knowledge_card(client, source_document(), PUBLIC_SCOPE)
    assert len(calls) == 1 and len(failure.value.attempts) == 1
    assert failure.value.attempts[0].outcome == code


def test_shared_generation_client_once_keeps_wire_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    source = source_document()
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source)]})
    draft = extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert len(calls) == 1 and len(draft.attempts) == 1
    assert draft.attempts[0].call_id == "synthetic-r09-call"
    assert draft.attempts[0].fee == "unknown" and draft.attempts[0].usage.total_tokens is None
    assert draft.verification_level == "unknown"


@pytest.mark.parametrize(
    "candidate",
    [
        {"field_name": "tenant_id", "value": "x", "citations": []},
        {"field_name": "input_path", "value": "x", "citations": []},
        {"field_name": "input_path", "value": " ", "citations": []},
        {"field_name": "input_path", "value": "x\0", "citations": []},
        {"field_name": "input_path", "value": "x" * 2001, "citations": []},
    ],
)
def test_strict_bounded_model_schema(candidate: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        output([candidate])
