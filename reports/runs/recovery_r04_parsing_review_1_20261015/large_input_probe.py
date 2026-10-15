"""Use the actual frozen parser limits with safe synthetic resource inputs."""
from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ai_intel.ingestion.parsing.parsers import parse_json_document, parse_pdf_text_layer
from independent_probe import independent_pdf


def main() -> None:
    checks: list[dict[str, object]] = []
    content = independent_pdf(["A" * 49000] * 21)
    start = time.monotonic()
    result = parse_pdf_text_layer(content)
    checks.append({"name": "actual_million_character_limit", "passed": result.status == "partial" and len(result.blocks) == 20 and len(result.normalized_text) == 980000 and result.notes == ("pdf text limit exceeded",), "input_bytes": len(content), "status": result.status, "blocks": len(result.blocks), "returned_characters": len(result.normalized_text), "notes": result.notes, "seconds": time.monotonic() - start})
    writer = PdfWriter()
    page = writer.add_blank_page(595, 842)
    page[NameObject("/Resources")] = DictionaryObject()
    stream = DecodedStreamObject()
    stream.set_data(b" " * (9 * 1024 * 1024))
    page[NameObject("/Contents")] = stream.flate_encode()
    output = BytesIO()
    writer.write(output)
    limited = parse_pdf_text_layer(output.getvalue())
    checks.append({"name": "actual_9MiB_compressed_stream_not_fulltext", "passed": limited.status == "unparseable" and not limited.blocks and any("failed" in note or "limited" in note for note in limited.notes), "input_bytes": len(output.getvalue()), "status": limited.status, "notes": limited.notes})
    json_limited = parse_json_document(b" " * (32 * 1024 * 1024 + 1))
    checks.append({"name": "actual_JSON_32MiB_input_limit", "passed": json_limited.status == "unparseable" and json_limited.notes == ("json input limit exceeded",), "status": json_limited.status, "notes": json_limited.notes})
    report = {"checks": checks, "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks)}
    Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
