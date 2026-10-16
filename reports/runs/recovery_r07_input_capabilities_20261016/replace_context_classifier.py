"""Remove the temporary copied qualifier parser in favor of authoritative typed gaps."""

from pathlib import Path

root = Path(__file__).resolve().parents[3]
path = root / "backend/src/ai_intel/enrichment/model_fields.py"
source = path.read_text(encoding="utf-8")
start = source.index("def _omitted_required_context(")
end = source.index("\n\ndef _generate_field", start)
replacement = '''def _omitted_required_context(
    error: FieldEvidenceError, selection: FieldEvidenceSelection
) -> bool:
    """Only gaps emitted after complete value validation can explain blocked selection."""
    return selection.incomplete and bool(error.context_gaps) and all(
        any(
            item.revision_id == gap.revision_id and item.block_id == gap.block_id
            and item.start_offset < gap.end_offset and gap.start_offset < item.end_offset
            for item in selection.omitted_ranges
        )
        for gap in error.context_gaps
    )
'''
source = source[:start] + replacement + source[end:]
source = source.replace("import re\n", "")
source = source.replace("error.code, proposed_candidate, documents, selection", "error, selection")
path.write_text(source, encoding="utf-8")
