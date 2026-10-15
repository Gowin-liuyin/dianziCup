"""派生分块仍可逐字定位原证据，不把块标识伪作永久证据。"""

from uuid import UUID

import pytest

from ai_intel.retrieval.service import split_evidence_quote


@pytest.mark.parametrize(
    "quote", ["首段风险\r\n第二段修复", "a\nb\rc\u2028d\u2029e", "汉" * 501, "  \nquoted words\n  "]
)
def test_every_chunk_is_exact_relative_quote_slice(quote: str) -> None:
    evidence_id = UUID("00000000-0000-4000-8000-000000000001")
    revision_id = UUID("00000000-0000-4000-8000-000000000002")
    chunks = split_evidence_quote(evidence_id, revision_id, quote)
    assert chunks
    assert chunks == split_evidence_quote(evidence_id, revision_id, quote)
    for chunk in chunks:
        assert quote[chunk.start_offset : chunk.end_offset] == chunk.text
        assert "\n" not in chunk.text and "\r" not in chunk.text
        assert chunk.evidence_id == evidence_id and chunk.revision_id == revision_id
        assert 0 < len(chunk.text) <= 240
        assert chunk.chunk_id != str(evidence_id)
