"""Validate extractive field evidence without treating a model proposal as a supported fact."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import ValidationError

from ai_intel.domain.enrichment_values import (
    ArtifactReferenceValue,
    AtlasMappingValue,
    LiteratureReferenceValue,
    VersionAssertionValue,
)
from ai_intel.domain.enums import ClaimOrigin, DocumentKind, SourceCategory
from ai_intel.enrichment.contracts import (
    CandidateEvidence,
    EnrichmentContext,
    EnrichmentDocument,
    EvidenceBoundCandidate,
)

MODEL_LIMITATION = (
    "Model proposal only; source identity and extractive checks do not confirm truth."
)
PARTIAL_LIMITATION = "Source coverage is incomplete; metadata or excerpts are not full text."


class FieldEvidenceError(ValueError):
    """Fixed safe error codes identify failed checks without exposing source text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_documents(
    context: EnrichmentContext, documents: tuple[EnrichmentDocument, ...]
) -> tuple[EnrichmentDocument, ...]:
    """Accept only the service-selected immutable revisions, never model-selected identities."""
    try:
        context = EnrichmentContext.model_validate(context.model_dump())
        documents = tuple(
            EnrichmentDocument.model_validate(document.model_dump()) for document in documents
        )
    except (AttributeError, ValidationError, UnicodeError):
        raise FieldEvidenceError("field_documents_invalid") from None
    if len(documents) > 20 or len({document.revision_id for document in documents}) != len(
        documents
    ):
        raise FieldEvidenceError("field_documents_invalid")
    for document in documents:
        if document.revision_id not in context.revision_ids:
            raise FieldEvidenceError("field_revision_outside_context")
        if document.document_kind == DocumentKind.ASSET_INVENTORY:
            raise FieldEvidenceError("field_asset_inventory_forbidden")
        if any("\0" in block.text for block in document.blocks):
            raise FieldEvidenceError("field_documents_invalid")
    return documents


def validate_evidence(
    evidence: tuple[CandidateEvidence, ...], documents: tuple[EnrichmentDocument, ...]
) -> tuple[EnrichmentDocument, ...]:
    """Coordinates are block-relative; complete lines preserve local negation and conditions."""
    by_revision = {document.revision_id: document for document in documents}
    selected: dict[UUID, EnrichmentDocument] = {}
    seen: set[tuple[UUID, UUID, int, int]] = set()
    for quote in evidence:
        CandidateEvidence.model_validate(quote.model_dump())
        document = by_revision.get(quote.revision_id)
        if document is None:
            raise FieldEvidenceError("field_evidence_revision_invalid")
        blocks = {block.block_id: block for block in document.blocks}
        block = blocks.get(quote.block_id)
        if block is None or block.text[quote.start_offset : quote.end_offset] != quote.quote_text:
            raise FieldEvidenceError("field_evidence_quote_invalid")
        identity = (quote.revision_id, quote.block_id, quote.start_offset, quote.end_offset)
        if identity in seen:
            raise FieldEvidenceError("field_evidence_duplicate")
        seen.add(identity)
        if (quote.start_offset and block.text[quote.start_offset - 1] not in "\r\n") or (
            quote.end_offset < len(block.text) and block.text[quote.end_offset] not in "\r\n"
        ):
            raise FieldEvidenceError("field_evidence_context_truncated")
        selected[document.revision_id] = document
    return tuple(selected.values())


def is_atlas_taxonomy(document: EnrichmentDocument) -> bool:
    """The trusted loader must bind the official artifact URI to its full commit identity."""
    parsed = urlsplit(str(document.canonical_uri))
    paths = {
        "raw.githubusercontent.com": r"/mitre/atlas-data/([0-9a-f]{40})/dist/ATLAS\.yaml",
        "github.com": r"/mitre/atlas-data/blob/([0-9a-f]{40})/dist/ATLAS\.yaml",
    }
    path_pattern = paths.get(parsed.hostname or "")
    pinned = re.fullmatch(path_pattern, parsed.path) if path_pattern else None
    return bool(
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and parsed.port in (None, 443)
        and not parsed.query
        and not parsed.fragment
        and pinned
        and document.source_version == pinned[1]
        and document.content_coverage == "full_text"
        and document.blocks_complete
    )


def _require_text(text: str, quotes: tuple[str, ...]) -> None:
    if not any(text.casefold() in quote.casefold() for quote in quotes):
        raise FieldEvidenceError("field_value_not_in_evidence")


def _require_identifier(text: str, quotes: tuple[str, ...]) -> None:
    pattern = re.compile(r"(?<![\w.+-])" + re.escape(text) + r"(?![\w.+-])", re.IGNORECASE)
    if not any(pattern.search(quote) for quote in quotes):
        raise FieldEvidenceError("field_identifier_not_in_evidence")


def _require_uri(uri: str, quotes: tuple[str, ...]) -> None:
    pattern = re.compile(re.escape(uri) + r"(?=$|[\s\]\)<>\"'])")
    if not any(pattern.search(quote) for quote in quotes):
        raise FieldEvidenceError("field_uri_not_in_evidence")


def _validate_atlas(
    value: AtlasMappingValue,
    evidence: tuple[CandidateEvidence, ...],
    documents: tuple[EnrichmentDocument, ...],
) -> AtlasMappingValue:
    taxonomy = tuple(document for document in documents if is_atlas_taxonomy(document))
    versions = {document.source_version for document in taxonomy}
    if value.taxonomy_version not in versions:
        raise FieldEvidenceError("atlas_taxonomy_version_invalid")
    taxonomy_revisions = {
        document.revision_id
        for document in taxonomy
        if document.source_version == value.taxonomy_version
    }
    taxonomy_quotes = tuple(
        quote.quote_text for quote in evidence if quote.revision_id in taxonomy_revisions
    )
    _require_identifier(value.technique_id, taxonomy_quotes)
    event_quotes = tuple(
        quote.quote_text for quote in evidence if quote.revision_id not in taxonomy_revisions
    )
    if value.mechanism not in event_quotes:
        raise FieldEvidenceError("atlas_mechanism_context_missing")
    event_blocks = tuple(
        block.text
        for document in documents
        if document.revision_id not in taxonomy_revisions
        for block in document.blocks
        if value.mechanism in block.text
    )
    prerequisites = tuple(
        line
        for block_text in event_blocks
        for line in block_text.splitlines()
        if re.search(r"attacker can|prerequisite|requires|前提|前置条件", line, re.IGNORECASE)
    )
    for source_prerequisite in prerequisites:
        if not any(source_prerequisite in item for item in value.prerequisites):
            raise FieldEvidenceError("atlas_prerequisite_context_missing")
    for prerequisite in value.prerequisites:
        _require_text(prerequisite, event_quotes)
    return value


def _require_version_qualifiers(
    raw_expression: str, evidence: tuple[CandidateEvidence, ...], document: EnrichmentDocument
) -> None:
    """Retain explicit qualifiers and wrapped continuations in the quoted source paragraph."""
    for quote in evidence:
        if quote.quote_text != raw_expression:
            continue
        block = next(block for block in document.blocks if block.block_id == quote.block_id)
        separators = tuple(re.finditer(r"\r?\n[ \t]*\r?\n", block.text))
        start = max(
            (item.end() for item in separators if item.end() <= quote.start_offset), default=0
        )
        end = next(
            (item.start() for item in separators if item.start() >= quote.end_offset),
            len(block.text),
        )
        paragraph = block.text[start:end]
        for marker in re.finditer(
            r"\b(?:only\s+(?:when|if|with)|requires?|required|prerequisites?|"
            r"provided\s+that|unless|conditional\s+on)\b|^[ \t]*(?:if|when)\b|"
            r"只有|仅当|前提|前置条件|必须|需要|除非",
            paragraph,
            re.IGNORECASE | re.MULTILINE,
        ):
            line_start = paragraph.rfind("\n", 0, marker.start()) + 1
            lines = paragraph[line_start:].splitlines(keepends=True)
            last = 0
            while last + 1 < len(lines) and not re.search(r"[.!?。！？]\s*$", lines[last]):
                last += 1
            qualifier = "".join(lines[: last + 1]).rstrip("\r\n")
            if qualifier not in raw_expression:
                raise FieldEvidenceError("version_expression_context_missing")


def _validate_versions(
    value: VersionAssertionValue,
    evidence: tuple[CandidateEvidence, ...],
    documents: tuple[EnrichmentDocument, ...],
) -> VersionAssertionValue:
    value = VersionAssertionValue.model_validate(value.model_dump())
    quotes = tuple(quote.quote_text for quote in evidence)
    if len(documents) != 1:
        raise FieldEvidenceError("version_cross_document_fields")
    _require_identifier(value.package_key, (value.raw_expression,))
    _require_identifier(value.ecosystem, quotes)
    if value.raw_expression not in quotes:
        raise FieldEvidenceError("version_expression_context_missing")
    _require_version_qualifiers(value.raw_expression, evidence, documents[0])
    if value.intervals or value.explicit_versions:
        if re.search(
            r"not affected|not vulnerable|unaffected|unknown|uncertain|no evidence|"
            r"不受影响|未受影响|未知|尚未确认",
            value.raw_expression,
            re.IGNORECASE,
        ):
            raise FieldEvidenceError("version_negative_or_unknown_range")
        if not re.search(r"affected|vulnerable|受影响", value.raw_expression, re.IGNORECASE):
            raise FieldEvidenceError("version_affected_scope_missing")
        for interval in value.intervals:
            for boundary, expression in (
                (interval.introduced, r">=\s*{}(?![\w.+-])|introduced\s*[:=]?\s*{}(?![\w.+-])"),
                (interval.fixed, r"(?<![<])<\s*{}(?![\w.+-])|fixed in\s+{}(?![\w.+-])"),
                (
                    interval.last_affected,
                    r"<=\s*{}(?![\w.+-])|last affected\s*[:=]?\s*{}(?![\w.+-])",
                ),
            ):
                if boundary is not None and not re.search(
                    expression.format(re.escape(boundary), re.escape(boundary)),
                    value.raw_expression,
                    re.IGNORECASE,
                ):
                    raise FieldEvidenceError("version_boundary_not_supported")
            if interval.branch is not None:
                _require_text(interval.branch, (value.raw_expression,))
        for version in value.explicit_versions:
            explicit = re.search(
                r"affected versions?\s*:\s*([^;\n]+)", value.raw_expression, re.IGNORECASE
            )
            if (
                explicit is None
                or any(operator in explicit[1] for operator in ("<", ">"))
                or (
                    not re.search(
                        r"(?<![\w.+-])" + re.escape(version) + r"(?![\w.+-])", explicit[1]
                    )
                )
            ):
                raise FieldEvidenceError("version_explicit_not_supported")
    if value.vendor_fix is not None:
        if documents[0].source_category != SourceCategory.VENDOR_ADVISORY:
            raise FieldEvidenceError("version_vendor_authority_missing")
        if value.vendor_fix not in quotes or not re.search(
            r"^(?:fix(?:ed)?|patch(?:ed)?|upgrade|修复|补丁)\b", value.vendor_fix, re.IGNORECASE
        ):
            raise FieldEvidenceError("version_vendor_fix_not_supported")
        if re.search(
            r"not fixed|no fix|unconfirmed|未修复|无补丁|未知", value.vendor_fix, re.IGNORECASE
        ):
            raise FieldEvidenceError("version_vendor_fix_not_supported")
    for mitigation in value.mitigations:
        if mitigation not in quotes or not re.search(
            r"^(?:mitigation|workaround|缓解|临时措施)\b", mitigation, re.IGNORECASE
        ):
            raise FieldEvidenceError("version_mitigation_not_supported")
    if value.comparison_support == "supported":
        raise FieldEvidenceError("version_model_comparison_forbidden")
    if value.scheme != "unknown":
        expected = {"pypi": "pep440", "npm": "semver", "git": "git"}.get(value.ecosystem.casefold())
        if value.scheme != expected:
            _require_text(value.scheme, quotes)
    comparable_schemes = {"pypi": "pep440", "npm": "semver"}
    support = (
        "unknown"
        if comparable_schemes.get(value.ecosystem.casefold()) == value.scheme
        else "unsupported"
    )
    return value.model_copy(update={"comparison_support": support})


def _validate_literature(
    value: LiteratureReferenceValue,
    quotes: tuple[str, ...],
    documents: tuple[EnrichmentDocument, ...],
    all_documents: tuple[EnrichmentDocument, ...],
) -> LiteratureReferenceValue:
    value = LiteratureReferenceValue.model_validate(value.model_dump())
    if value.target_document_id is not None or value.target_revision_id is not None:
        raise FieldEvidenceError("literature_model_identity_forbidden")
    _require_uri(str(value.uri), quotes)
    _require_text(value.title, quotes)
    _require_text(value.support_summary, quotes)
    if not any(str(value.uri) in quote and value.title in quote for quote in quotes):
        raise FieldEvidenceError("literature_title_uri_binding_missing")
    if value.relation != "background":
        if any(
            not document.blocks_complete or document.content_coverage != "full_text"
            for document in documents
        ):
            raise FieldEvidenceError("literature_fulltext_required")
        markers = {
            "analysis": r"analy[sz]|分析",
            "defense": r"defen[sc]e|mitigat|防御|缓解",
            "experimental": r"experiment|实验",
        }
        if not re.search(markers[value.relation], value.support_summary, re.IGNORECASE):
            raise FieldEvidenceError("literature_relation_not_supported")
    targets = tuple(document for document in all_documents if document.canonical_uri == value.uri)
    if len(targets) > 1:
        raise FieldEvidenceError("literature_target_revision_ambiguous")
    if targets:
        target = targets[0]
        expected_kind = {
            "paper": DocumentKind.PAPER,
            "article": DocumentKind.ARTICLE,
            "standard": DocumentKind.STANDARD,
            "policy": DocumentKind.POLICY,
        }[value.reference_kind]
        if target.document_kind != expected_kind:
            raise FieldEvidenceError("literature_target_kind_mismatch")
        _require_text(value.title, tuple(block.text for block in target.blocks))
        if value.relation != "background" and (
            not target.blocks_complete or target.content_coverage != "full_text"
        ):
            raise FieldEvidenceError("literature_target_fulltext_required")
        return value.model_copy(
            update={
                "target_document_id": target.document_id,
                "target_revision_id": target.revision_id,
            }
        )
    return value


def _validate_poc(value: ArtifactReferenceValue, quotes: tuple[str, ...]) -> ArtifactReferenceValue:
    value = ArtifactReferenceValue.model_validate(value.model_dump())
    _require_uri(str(value.uri), quotes)
    _require_text(value.title, quotes)
    if not any(str(value.uri) in quote and value.title in quote for quote in quotes):
        raise FieldEvidenceError("poc_title_uri_binding_missing")
    if value.static_status != "candidate_found":
        raise FieldEvidenceError("poc_model_review_forbidden")
    kind_markers = {
        "poc": r"\bpoc\b|proof.of.concept|概念验证",
        "detection_template": r"detection template|检测模板",
        "analysis_repository": r"analysis repository|分析仓库",
    }
    if not any(
        re.search(kind_markers[value.artifact_kind], quote, re.IGNORECASE)
        and str(value.uri) in quote
        for quote in quotes
    ):
        raise FieldEvidenceError("poc_kind_not_supported")
    if value.commit_sha is not None:
        _require_identifier(value.commit_sha, quotes)
    if value.artifact_path is not None:
        _require_text(value.artifact_path, quotes)
    if value.license_identifier is not None:
        _require_identifier(value.license_identifier, quotes)
        if not any(
            re.search(r"licen[cs]e|许可证|许可协议", quote, re.IGNORECASE)
            and value.license_identifier in quote
            for quote in quotes
        ):
            raise FieldEvidenceError("poc_license_binding_missing")
    if (
        value.commit_sha is not None
        and value.commit_sha not in str(value.uri)
        and not any("commit" in quote.casefold() and value.commit_sha in quote for quote in quotes)
    ):
        raise FieldEvidenceError("poc_commit_binding_missing")
    return value


def validate_field_candidate(
    candidate: EvidenceBoundCandidate, documents: tuple[EnrichmentDocument, ...]
) -> EvidenceBoundCandidate:
    """Field checks reject invention; surviving candidates remain model hypotheses for review."""
    EvidenceBoundCandidate.model_validate(candidate.model_dump())
    selected = validate_evidence(candidate.evidence, documents)
    quotes = tuple(quote.quote_text for quote in candidate.evidence)
    value = candidate.value
    if isinstance(value, AtlasMappingValue):
        value = _validate_atlas(value, candidate.evidence, selected)
    elif isinstance(value, VersionAssertionValue):
        value = _validate_versions(value, candidate.evidence, selected)
    elif isinstance(value, LiteratureReferenceValue):
        value = _validate_literature(value, quotes, selected, documents)
    elif isinstance(value, ArtifactReferenceValue):
        value = _validate_poc(value, quotes)
    else:
        raise FieldEvidenceError("field_dimension_not_owned")
    if isinstance(value, (VersionAssertionValue, LiteratureReferenceValue, ArtifactReferenceValue)):
        for limitation in value.limitations:
            _require_text(limitation, quotes)
    limitations = [MODEL_LIMITATION]
    if any(not item.blocks_complete or item.content_coverage != "full_text" for item in selected):
        limitations.append(PARTIAL_LIMITATION)
    if isinstance(value, ArtifactReferenceValue):
        limitations.append("Link metadata only; no repository fetched, executed, or verified.")
    return candidate.model_copy(
        update={
            "value": value,
            "origin": ClaimOrigin.MODEL_HYPOTHESIS,
            "limitations": tuple(limitations),
        }
    )


def quote_digest(quote_text: str) -> str:
    return hashlib.sha256(quote_text.encode()).hexdigest()
