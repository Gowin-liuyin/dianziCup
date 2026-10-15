"""R02知识纯判断回归; fixture不计为真实持久化验证。"""

from dataclasses import replace

import pytest

from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.structured import Claim, EnrichmentConflictError, EnrichmentLedger
from ai_intel.ingestion.parsing.text_blocks import TextBlock
from ai_intel.knowledge.claims import ClaimsContractError, ClaimsLedger
from ai_intel.knowledge.event_linking import EventLinkingError, EventLinkingLedger, SecurityEvent
from ai_intel.knowledge.evidence import (
    AmbiguousQuoteError,
    locate_evidence_span,
    render_revision_snippet,
)


def test_repeated_quote_in_one_block_requires_occurrence() -> None:
    block = TextBlock("b", 1, "paragraph", "共同句，共同句", 100, 107)
    with pytest.raises(AmbiguousQuoteError):
        locate_evidence_span((block,), "共同句", "b")
    located = locate_evidence_span((block,), "共同句", "b", start_offset=104)
    assert (located.start_offset, located.end_offset) == (104, 107)
    with pytest.raises(ValueError, match="occurrence"):
        locate_evidence_span((block,), "共同句", "b", start_offset=103)
    with pytest.raises(ValueError, match="requires block_id"):
        locate_evidence_span((block,), "共同句", start_offset=104)


def test_same_article_hash_does_not_merge_different_events() -> None:
    ledger = EventLinkingLedger(fixture_mode=True)
    left = SecurityEvent("a", cve_ids=("CVE-2025-0001",), body_fingerprint="same")
    right = SecurityEvent("b", cve_ids=("CVE-2025-0002",), body_fingerprint="same")
    assert ledger.should_merge(left, right, ()) is False


def test_render_rejects_tampered_source_at_same_coordinate() -> None:
    block = TextBlock("b", 1, "paragraph", "original", 100, 108)
    located = locate_evidence_span((block,), "original", "b")
    tampered = replace(block, text="modified")
    scope = AccessScope.for_authenticated_user("user", "tenant-a", Role.VIEWER)
    with pytest.raises(ValueError, match="hash"):
        render_revision_snippet((tampered,), located, scope, "public", None)


@pytest.mark.parametrize("field", ["source_revision_id", "json_path", "scoring_authority", "scope"])
def test_field_deduplication_includes_provenance(field: str) -> None:
    ledger = EnrichmentLedger(fixture_mode=True)
    first = Claim("cvss_score", "8.1", "source", "$.score", scoring_authority="CNA")
    second = replace(first, **{field: "different"})
    ledger.apply_claims("input", [first, second], "vulnerability_advisory")
    assert len(ledger.facts["cvss_score"]) == 2


def test_failed_batch_validation_does_not_consume_fingerprint(monkeypatch) -> None:
    ledger = EnrichmentLedger(fixture_mode=True)
    first = Claim("cvss_score", "8.1", "source", "$.score")
    second = Claim("fix_status", "fixed", "source", "$.fix")

    def failing_status(dimension: str, document_kind: str) -> str:
        if dimension == "fix_status":
            raise ValueError("synthetic invalid dimension")
        return "available"

    with monkeypatch.context() as patcher:
        patcher.setattr("ai_intel.enrichment.structured.dimension_status_for_kind", failing_status)
        with pytest.raises(ValueError):
            ledger.apply_claims("input", [first, second], "vulnerability_advisory")
    assert ledger.facts == {}
    assert "input" not in ledger.processed_input_fingerprints
    assert ledger.apply_claims("input", [first, second], "vulnerability_advisory") == "applied"


@pytest.mark.parametrize(
    "ledger,error",
    [
        (ClaimsLedger, ClaimsContractError),
        (EnrichmentLedger, EnrichmentConflictError),
        (EventLinkingLedger, EventLinkingError),
    ],
)
def test_memory_ledgers_require_explicit_fixture_mode(ledger, error) -> None:
    with pytest.raises(error, match="fixture_mode"):
        ledger()
