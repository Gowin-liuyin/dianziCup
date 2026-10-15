"""Require a real Font resource so the oversized Flate stream is decoded."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ai_intel.ingestion.parsing.parsers import parse_pdf_text_layer


writer = PdfWriter()
page = writer.add_blank_page(595, 842)
font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
stream = DecodedStreamObject()
decoded = b"BT /F1 12 Tf 20 700 Td (text beyond safe stream budget) Tj ET " + b" " * (9 * 1024 * 1024)
stream.set_data(decoded)
page[NameObject("/Contents")] = stream.flate_encode()
output = BytesIO()
writer.write(output)
result = parse_pdf_text_layer(output.getvalue())
passed = result.status == "unparseable" and not result.blocks and result.notes == ("page 1: text extraction failed",)
report = {"passed": passed, "input_bytes": len(output.getvalue()), "decoded_bytes": len(decoded), "status": result.status, "notes": result.notes, "reliable_resources_present": True}
Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if passed else 1)
