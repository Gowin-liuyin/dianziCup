"""Independent observable probes; no product source, secrets, or gold data changes."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ai_intel.ingestion.parsing import pdf_text
from ai_intel.ingestion.parsing.parsers import parse_json_document, parse_pdf_text_layer
from ai_intel.knowledge.evidence import locate_evidence_span

OUTPUT = Path(__file__).resolve().parent
REPO = Path.cwd().parent
checks: list[dict[str, object]] = []


def record(name: str, passed: bool, detail: object) -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


def independent_pdf(pages: list[str | None], *, encrypt: bool = False) -> bytes:
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(595, 842)
        if text is not None:
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
            stream = DecodedStreamObject()
            literal = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.set_data(("BT /F1 11 Tf 30 700 Td (" + literal + ") Tj ET").encode("ascii"))
            page[NameObject("/Contents")] = stream
    if encrypt:
        writer.encrypt("review-only-synthetic-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def main() -> None:
    official = REPO / "docs/references/competition_brief.pdf"
    start = time.monotonic()
    outcome = parse_pdf_text_layer(official.read_bytes())
    record("official_4_pages", outcome.status == "parsed" and [b.page_number for b in outcome.blocks] == [1, 2, 3, 4], {"status": outcome.status, "pages": [b.page_number for b in outcome.blocks], "characters": len(outcome.normalized_text), "seconds_single_diagnostic": time.monotonic() - start})
    quotes = ["智能体驱动的 AI 安全知识情报系统设计与实现", "六、评价指标", "线下决赛", "八、参赛平台"]
    for block, quote in zip(outcome.blocks, quotes, strict=True):
        try:
            span = locate_evidence_span(outcome.blocks, quote, block_id=block.block_id)
            match = outcome.normalized_text[span.start_offset:span.end_offset] == quote
            record("official_page_quote_" + str(block.page_number), match, {"quote": quote, "start": span.start_offset, "end": span.end_offset, "page": block.page_number})
        except ValueError as error:
            record("official_page_quote_" + str(block.page_number), False, {"quote": quote, "error": type(error).__name__})
    fixture = REPO / "fixtures/synthetic/pdf_image_only_test.pdf"
    blob = subprocess.check_output(["git", "show", "HEAD:fixtures/synthetic/pdf_image_only_test.pdf"], cwd=REPO)
    content = fixture.read_bytes()
    reader = PdfReader(BytesIO(content), strict=True)
    image = next(iter(reader.pages[0]["/Resources"]["/XObject"].values())).get_object()
    record("fresh_checkout_binary_fixture", blob == content and len(reader.pages) == 1 and image["/Width"] == image["/Height"] == 1, {"size": len(content), "sha256": hashlib.sha256(content).hexdigest(), "blob_equal": blob == content, "width": image["/Width"], "height": image["/Height"], "startxref": content[content.rfind(b"startxref"):].decode("ascii")})
    cases = {"blank_pdf": independent_pdf([None]), "zero_page_pdf": independent_pdf([]), "mixed_pages": independent_pdf(["page one", None, "page three"]), "encrypted_pdf": independent_pdf(["private synthetic"], encrypt=True), "301_pages": independent_pdf([None] * 301), "corrupt_pdf": b"%PDF-1.7\n1 0 obj << /Broken true >>\n", "fake_TEXTLAYER": b"%PDF-1.4\nTEXTLAYER:should never be accepted\n%%EOF"}
    for name, raw in cases.items():
        result = parse_pdf_text_layer(raw)
        expected_status = "partial" if name == "mixed_pages" else "unparseable"
        passed = result.status == expected_status and (name == "mixed_pages" or not result.blocks)
        if name == "mixed_pages":
            passed = passed and [b.page_number for b in result.blocks] == [1, 3] and "page 2: no reliable text layer; OCR not performed" in result.notes
        record(name, passed, {"status": result.status, "pages": [b.page_number for b in result.blocks], "notes": result.notes})
    raw = b"%PDF-1.4" + b"x" * (32 * 1024 * 1024)
    result = parse_pdf_text_layer(raw)
    record("oversize_input_rejected", result.notes == ("pdf input limit exceeded",), {"size": len(raw), "notes": result.notes})
    negative_json = {"duplicate_nested": b'{"a":{"x":1,"x":2}}', "NaN": b'{"x":NaN}', "Infinity": b'{"x":Infinity}', "overflow": b'{"x":1e999}', "bad_UTF8": b'\xff', "invalid_structure": b'{"x":[1,]}', "depth33": b'[' * 33 + b'0' + b']' * 33, "10001_leaves": json.dumps(list(range(10001))).encode()}
    for name, raw in negative_json.items():
        result = parse_json_document(raw)
        record("json_reject_" + name, result.status == "unparseable" and not result.blocks, {"status": result.status, "notes": result.notes})
    pointer_result = parse_json_document('{"a/b":{"~name":[{"文":"引用文本"}]}}'.encode())
    record("json_pointer_escaping", pointer_result.blocks[0].block_type == "field:/a~1b/~0name/0/文", pointer_result.blocks[0].block_type)
    actual_value = '中文\n版本 "1.2" 路径 C:\\app'
    string_result = parse_json_document(json.dumps({"description": actual_value}, ensure_ascii=False).encode())
    try:
        span = locate_evidence_span(string_result.blocks, actual_value, block_id=string_result.blocks[0].block_id)
        quoted = string_result.normalized_text[span.start_offset:span.end_offset] == actual_value
        error_name = None
    except ValueError as error:
        quoted = False
        error_name = type(error).__name__
    record("json_original_unicode_value_quote", quoted, {"status": string_result.status, "actual_value": actual_value, "normalized_text": string_result.normalized_text, "exception": error_name})
    surrogate = parse_json_document(b'{"description":"\\ud800"}')
    try:
        surrogate.normalized_text.encode("utf-8")
        encodeable = True
    except UnicodeEncodeError:
        encodeable = False
    record("json_lone_surrogate_fail_closed", surrogate.status == "unparseable" or encodeable, {"status": surrogate.status, "utf8_encodeable": encodeable})
    memory_code = "from ai_intel.ingestion.parsing._pdf_worker import _bound_memory; import json; handle = _bound_memory(); small=bytearray(32*1024*1024); limited=False\ntry:\n large=bytearray(600*1024*1024)\nexcept MemoryError:\n limited=True\nprint(json.dumps({'native_32MiB_success':len(small)==32*1024*1024,'native_600MiB_refused':limited,'job_handle_present':handle is not None}))\nraise SystemExit(0 if limited else 1)"
    native = subprocess.run([sys.executable, "-c", memory_code], capture_output=True, timeout=10, check=False)
    memory_detail = json.loads(native.stdout) if native.returncode == 0 else {"returncode": native.returncode, "error_type_only": "native probe failed"}
    record("native_memory_512MiB_observable_boundary", native.returncode == 0 and memory_detail.get("native_600MiB_refused") is True, memory_detail)
    original_popen = pdf_text.subprocess.Popen
    native_processes: list[subprocess.Popen[bytes]] = []
    both_started = threading.Event()
    lock = threading.Lock()
    environment_checks: list[bool] = []

    def held_native_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = original_popen(*args, **kwargs)
        with lock:
            native_processes.append(child)
            environment_checks.append("DIANZI_REVIEW_SECRET" not in kwargs["env"])
            if len(native_processes) == 2:
                both_started.set()
        both_started.wait(5)
        return child

    with patch.dict(os.environ, {"DIANZI_REVIEW_SECRET": "synthetic-review-marker"}), patch.object(pdf_text.subprocess, "Popen", held_native_popen):
        with ThreadPoolExecutor(max_workers=3) as executor:
            first = executor.submit(parse_pdf_text_layer, cases["mixed_pages"])
            second = executor.submit(parse_pdf_text_layer, cases["mixed_pages"])
            both_started.wait(5)
            third = parse_pdf_text_layer(cases["mixed_pages"])
            results = [first.result(), second.result()]
    record("two_live_native_workers_and_capacity_rejection", len(native_processes) == 2 and all(r.status == "partial" for r in results) and third.notes == ("pdf parser capacity reached",), {"workers": len(native_processes), "native_statuses": [r.status for r in results], "third_notes": third.notes, "reaped": [p.poll() is not None for p in native_processes]})
    record("synthetic_environment_secret_not_inherited", all(environment_checks), {"checks": environment_checks})
    report = {"platform": sys.platform, "python": sys.version.split()[0], "checks": checks, "passed": sum(c["passed"] is True for c in checks), "failed": sum(c["passed"] is False for c in checks)}
    (OUTPUT / "independent_probe_2.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
