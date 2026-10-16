"""Existing semantic validator distinguishes the full version proof from mitigation alone."""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_r10_evidence_graph_pg import VERSION

from ai_intel.enrichment.contracts import CandidateEvidence, EnrichmentBlock, EnrichmentDocument, EvidenceBoundCandidate
from ai_intel.enrichment.field_sources import FieldEvidenceError, validate_field_candidate


@pytest.mark.parametrize("complete", [True, False])
def test_declared_version_proof_requires_version_expression(complete):
    revision_id, block_id = uuid4(), uuid4()
    lines = [VERSION["raw_expression"], VERSION["vendor_fix"], *VERSION["mitigations"]]
    body = "\n".join(lines)
    document = EnrichmentDocument.model_validate({"revision_id": revision_id,
        "document_id": uuid4(), "source_id": uuid4(), "document_kind": "advisory",
        "source_category": "vendor_advisory", "canonical_uri": "https://example.invalid/fixture",
        "source_record_id": "synthetic-declared-evidence", "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "blocks": [EnrichmentBlock(block_id=block_id, start_offset=100, text=body,
            text_sha256=hashlib.sha256(body.encode()).hexdigest())], "blocks_complete": True,
        "content_coverage": "full_text", "observed_at": datetime.now(UTC)})
    quotes = []
    offset = 0
    for line in lines:
        if complete or line == lines[-1]:
            quotes.append(CandidateEvidence(revision_id=revision_id, block_id=block_id,
                start_offset=offset, end_offset=offset + len(line), quote_text=line,
                quote_sha256=hashlib.sha256(line.encode()).hexdigest()))
        offset += len(line) + 1
    candidate = EvidenceBoundCandidate.model_validate({"dimension": "versions",
        "value": {**VERSION, "comparison_support": "unknown"}, "evidence": quotes,
        "origin": "source_explicit"})
    if complete:
        result = validate_field_candidate(candidate, (document,))
        assert result.value.kind == "version_assertion"
    else:
        with pytest.raises(FieldEvidenceError):
            validate_field_candidate(candidate, (document,))
