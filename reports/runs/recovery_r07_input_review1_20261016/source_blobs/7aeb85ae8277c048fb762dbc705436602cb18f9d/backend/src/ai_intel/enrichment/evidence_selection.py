"""Deterministic field retrieval preserves immutable block coordinates and input budgets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import UUID

from ai_intel.domain.enrichment_values import DimensionName
from ai_intel.enrichment.contracts import CandidateEvidence, EnrichmentDocument
from ai_intel.enrichment.field_sources import FieldEvidenceError

SELECTION_VERSION = "r07-field-selection-1"
MAX_BLOCKS = 50
MAX_RECORD_CHARACTERS = 16384
MAX_INPUT_BYTES = 65536
SELECTION_REPORT_RESERVE = 4096
FIELD_CUES = {
    "versions": re.compile(
        r"version|affected|fixed|patch|upgrade|mitigation|workaround|ecosystem|"
        r"cpeMatch|vulnerable|ranges|版本|受影响|修复|缓解",
        re.IGNORECASE,
    ),
    "atlas": re.compile(
        r"AML\.T\d{4}|prompt|inject|untrusted|instruction|attacker|prerequisite|"
        r"requires|only when|only if|unless|提示|注入|攻击|前提|条件",
        re.IGNORECASE,
    ),
    "literature": re.compile(
        r"https?://|paper|article|standard|policy|research|analy[sz]|defen[sc]|"
        r"experiment|background|论文|文献|标准|政策|分析|防御|实验",
        re.IGNORECASE,
    ),
    "poc": re.compile(
        r"https?://|\bpoc\b|proof.of.concept|detection template|analysis repository|"
        r"commit|licen[sc]e|概念验证|检测模板|分析仓库",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class SelectedEvidenceRange:
    revision_id: UUID
    block_id: UUID
    start_offset: int
    end_offset: int
    matched_cues: tuple[str, ...]


@dataclass(frozen=True)
class SourceEvidenceVersion:
    revision_id: UUID
    document_id: UUID
    source_id: UUID
    content_sha256: str
    source_version: str | None
    canonical_uri: str


@dataclass(frozen=True)
class FieldEvidenceSelection:
    """Full source dependencies stay present even when no blocks from a source fit."""

    dimension: DimensionName
    texts: tuple[str, ...]
    selected: tuple[SelectedEvidenceRange, ...]
    omitted_block_ids: tuple[tuple[UUID, UUID], ...]
    omitted_ranges: tuple[SelectedEvidenceRange, ...]
    source_versions: tuple[SourceEvidenceVersion, ...]
    incomplete: bool
    selection_version: str = SELECTION_VERSION


def _record(document: EnrichmentDocument, block_index: int, start: int, end: int) -> str:
    block = document.blocks[block_index]
    return json.dumps(
        {
            "revision_id": str(document.revision_id),
            "document_id": str(document.document_id),
            "source_id": str(document.source_id),
            "canonical_uri": str(document.canonical_uri),
            "document_kind": document.document_kind.value,
            "source_category": document.source_category.value,
            "source_version": document.source_version,
            "content_sha256": document.content_sha256,
            "content_coverage": document.content_coverage,
            "blocks_complete": document.blocks_complete,
            "block_id": str(block.block_id),
            "block_text_sha256": block.text_sha256,
            "block_start_offset": block.start_offset,
            "start_offset": start,
            "end_offset": end,
            "text": block.text[start:end],
        },
        ensure_ascii=False,
    )


def select_field_evidence(
    documents: tuple[EnrichmentDocument, ...], dimension: DimensionName
) -> FieldEvidenceSelection:
    """Rank complete source blocks by field cues; oversized blocks use complete lines.

    This is lexical retrieval, not semantic support validation. Whole blocks that fit
    preserve qualifiers. An oversized line is never split into a misleading quotation.
    No-hit oversized input is unknown and raises a safe error, never a safety conclusion.
    """
    if dimension not in FIELD_CUES:
        raise FieldEvidenceError("field_dimension_invalid")
    cue_pattern = FIELD_CUES[dimension]
    candidates: list[tuple[int, int, int, int, int, tuple[str, ...], str]] = []
    full_records = tuple(
        _record(document, index, 0, len(block.text))
        for document in documents
        for index, block in enumerate(document.blocks)
    )
    full_fits = (
        len(full_records) < MAX_BLOCKS
        and all(len(record) <= MAX_RECORD_CHARACTERS for record in full_records)
        and sum(len(record.encode()) for record in full_records)
        <= MAX_INPUT_BYTES - SELECTION_REPORT_RESERVE
    )
    for document_index, document in enumerate(documents):
        for block_index, block in enumerate(document.blocks):
            record = _record(document, block_index, 0, len(block.text))
            ranges = [(0, len(block.text))]
            if len(record) > MAX_RECORD_CHARACTERS:
                ranges = []
                position = 0
                for line in block.text.splitlines(keepends=True):
                    content = line.rstrip("\r\n")
                    if content and len(content) <= 2000:
                        ranges.append((position, position + len(content)))
                    position += len(line)
            for start, end in ranges:
                cues = tuple(
                    sorted(
                        {hit[0].casefold() for hit in cue_pattern.finditer(block.text[start:end])}
                    )
                )
                if not full_fits and not cues:
                    continue
                candidates.append(
                    (
                        -len(cues),
                        document_index,
                        block_index,
                        start,
                        end,
                        cues,
                        _record(document, block_index, start, end),
                    )
                )
    candidates.sort(key=lambda item: item[:5])
    selected: list[SelectedEvidenceRange] = []
    records: list[str] = []
    used_bytes = 0
    for _, document_index, block_index, start, end, cues, record in candidates:
        record_bytes = len(record.encode())
        if (
            len(records) >= MAX_BLOCKS - 1
            or len(record) > MAX_RECORD_CHARACTERS
            or used_bytes + record_bytes > MAX_INPUT_BYTES - SELECTION_REPORT_RESERVE
        ):
            continue
        document = documents[document_index]
        block = document.blocks[block_index]
        selected.append(
            SelectedEvidenceRange(document.revision_id, block.block_id, start, end, cues)
        )
        records.append(record)
        used_bytes += record_bytes
    if not selected:
        raise FieldEvidenceError("field_input_budget_exhausted")
    selected_ids = {(item.revision_id, item.block_id) for item in selected}
    omitted = tuple(
        (document.revision_id, block.block_id)
        for document in documents
        for block in document.blocks
        if (document.revision_id, block.block_id) not in selected_ids
    )
    omitted_ranges: list[SelectedEvidenceRange] = []
    for document in documents:
        for block in document.blocks:
            ranges = sorted(
                (item.start_offset, item.end_offset)
                for item in selected
                if item.revision_id == document.revision_id and item.block_id == block.block_id
            )
            position = 0
            for start, end in ranges:
                if position < start:
                    omitted_ranges.append(
                        SelectedEvidenceRange(
                            document.revision_id,
                            block.block_id,
                            position,
                            start,
                            (),
                        )
                    )
                position = end
            if position < len(block.text):
                omitted_ranges.append(
                    SelectedEvidenceRange(
                        document.revision_id,
                        block.block_id,
                        position,
                        len(block.text),
                        (),
                    )
                )
    incomplete = bool(omitted_ranges) or any(
        not doc.blocks_complete or doc.content_coverage != "full_text" for doc in documents
    )
    report = {
        "selection_version": SELECTION_VERSION,
        "dimension": dimension,
        "incomplete": incomplete,
        "selected_ranges": len(selected),
        "omitted_blocks": len(omitted),
        "omitted_ranges": len(omitted_ranges),
        "source_revisions": [str(doc.revision_id) for doc in documents],
        "instruction": "Quotes use original block-relative Unicode offsets. Coverage is partial "
        "when incomplete; missing candidates are unknown, never a full-source negative.",
    }
    records.insert(0, json.dumps({"selection": report}, ensure_ascii=False))
    if (
        any(len(record) > MAX_RECORD_CHARACTERS for record in records)
        or sum(len(record.encode()) for record in records) > MAX_INPUT_BYTES
    ):
        raise FieldEvidenceError("field_input_budget_exhausted")
    return FieldEvidenceSelection(
        dimension,
        tuple(records),
        tuple(selected),
        omitted,
        tuple(omitted_ranges),
        tuple(
            SourceEvidenceVersion(
                doc.revision_id,
                doc.document_id,
                doc.source_id,
                doc.content_sha256,
                doc.source_version,
                str(doc.canonical_uri),
            )
            for doc in documents
        ),
        incomplete,
    )


def require_selected_evidence(
    evidence: tuple[CandidateEvidence, ...], selection: FieldEvidenceSelection
) -> None:
    """A model cannot quote a real but omitted span that was never in its input."""
    if any(
        not any(
            quote.revision_id == item.revision_id
            and quote.block_id == item.block_id
            and item.start_offset <= quote.start_offset < quote.end_offset <= item.end_offset
            for item in selection.selected
        )
        for quote in evidence
    ):
        raise FieldEvidenceError("field_evidence_outside_selection")
