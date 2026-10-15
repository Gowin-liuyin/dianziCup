"""Target the confirmed JSON failures and adjacent Unicode evidence boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.knowledge.evidence import AmbiguousQuoteError, locate_evidence_span

checks: list[dict[str, object]] = []


def record(name: str, passed: bool, detail: object) -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


original = '中文\n版本 "1.2" 路径 C:\\app 😀'
outcome = parse_json_document(json.dumps({"description": original}, ensure_ascii=False).encode())
span = locate_evidence_span(outcome.blocks, original, block_id=outcome.blocks[0].block_id)
record("original_whole_value_quote", outcome.status == "parsed" and outcome.normalized_text[span.start_offset:span.end_offset] == original, {"status": outcome.status, "start": span.start_offset, "end": span.end_offset, "characters": len(original), "parser": outcome.parser_version})
record("original_whole_value_hash", span.quote_sha256 == hashlib.sha256(original.encode()).hexdigest(), {"sha256": span.quote_sha256})
record("lossless_normalized_UTF8", outcome.normalized_text.encode().decode() == outcome.normalized_text, True)
path_value = 'path quote "😀"\nline 2'
pointer = parse_json_document(json.dumps({"a/b": {"~name": [{"😀": path_value}]}}, ensure_ascii=False).encode())
pointer_span = locate_evidence_span(pointer.blocks, path_value, block_id=pointer.blocks[0].block_id)
record("RFC6901_non_BMP_key_and_raw_value", pointer.blocks[0].block_type == "field:/a~1b/~0name/0/😀" and pointer.normalized_text[pointer_span.start_offset:pointer_span.end_offset] == path_value, pointer.blocks[0].block_type)
invalid = {"high_value": b'{"x":"\\ud800"}', "low_value": b'{"x":"\\udfff"}', "high_key": b'{"\\ud800":"value"}', "low_key": b'{"\\udfff":"value"}', "NUL_value": b'{"x":"\\u0000"}', "NUL_key": b'{"\\u0000":"value"}', "nested_invalid_value": b'{"x":[{"y":"\\ud800"}]}', "duplicate_escaped_key": b'{"x":1,"\\u0078":2}', "NaN_unchanged": b'{"x":NaN}', "overflow_unchanged": b'{"x":1e999}'}
for name, content in invalid.items():
    result = parse_json_document(content)
    record(name, result.status == "unparseable" and not result.blocks and result.notes == ("invalid json",), {"status": result.status, "notes": result.notes})
valid_pair = parse_json_document(b'{"\\ud83d\\ude00":"\\ud83d\\ude00"}')
record("valid_surrogate_pair_key_and_value", valid_pair.status == "parsed" and valid_pair.blocks[0].block_type == "field:/😀" and valid_pair.blocks[0].text == "/😀: 😀", {"status": valid_pair.status, "text": valid_pair.blocks[0].text})
repeated = parse_json_document(b'{"description":"repeat repeat"}')
try:
    locate_evidence_span(repeated.blocks, "repeat", block_id=repeated.blocks[0].block_id)
except AmbiguousQuoteError:
    ambiguous = True
else:
    ambiguous = False
record("same_leaf_repeated_quote_still_ambiguous", ambiguous, ambiguous)
position = repeated.blocks[0].text.rfind("repeat")
resolved = locate_evidence_span(repeated.blocks, "repeat", block_id=repeated.blocks[0].block_id, start_offset=position)
record("same_leaf_occurrence_global_offset", resolved.start_offset == position and repeated.normalized_text[resolved.start_offset:resolved.end_offset] == "repeat", {"start": resolved.start_offset, "end": resolved.end_offset})
report = {"passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks), "checks": checks}
Path(__file__).with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=True, indent=2))
raise SystemExit(1 if report["failed"] else 0)
