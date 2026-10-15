"""真实PDF字节与严格JSON定位的隔离边界测试，不计live采集或人工金标。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ai_intel.ingestion.parsing.parsers import parse_json_document, parse_pdf_text_layer
from ai_intel.knowledge.evidence import locate_evidence_span


def make_pdf(text_pages: tuple[str | None, ...], *, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for text in text_pages:
        page = writer.add_blank_page(width=600, height=800)
        if text is not None:
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {
                            NameObject("/F1"): DictionaryObject(
                                {
                                    NameObject("/Type"): NameObject("/Font"),
                                    NameObject("/Subtype"): NameObject("/Type1"),
                                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                                }
                            )
                        }
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 20 700 Td ({text}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("isolated-pdf-test-only")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_official_four_pages_have_real_chinese_text_and_exact_page_locator() -> None:
    source = Path(__file__).resolve().parents[3] / "docs/references/competition_brief.pdf"
    outcome = parse_pdf_text_layer(source.read_bytes())
    assert outcome.status == "parsed"
    assert [block.page_number for block in outcome.blocks] == [1, 2, 3, 4]
    quote = "智能体驱动的 AI 安全知识情报系统设计与实现"
    first = outcome.blocks[0]
    assert quote in first.text
    span = locate_evidence_span(outcome.blocks, quote, block_id=first.block_id)
    assert outcome.normalized_text[span.start_offset : span.end_offset] == quote
    assert first.page_number == 1
    assert outcome.parser_version == "pdf-2.0.0"


def test_pdf_keeps_missing_page_as_partial_without_renumbering() -> None:
    outcome = parse_pdf_text_layer(make_pdf(("first evidence", None, "third evidence")))
    assert outcome.status == "partial"
    assert [block.page_number for block in outcome.blocks] == [1, 3]
    assert "page 2: no reliable text layer; OCR not performed" in outcome.notes
    assert "third evidence" in outcome.normalized_text


def test_empty_and_encrypted_pdfs_never_become_successful_fulltext() -> None:
    empty = parse_pdf_text_layer(make_pdf((None,)))
    assert empty.status == "unparseable" and not empty.blocks
    encrypted = parse_pdf_text_layer(make_pdf(("protected evidence",), encrypted=True))
    assert encrypted.status == "unparseable" and not encrypted.blocks
    assert any("encrypted" in note for note in encrypted.notes)


@pytest.mark.parametrize(
    "content",
    [
        b"not pdf",
        b"%PDF-1.4\n%%EOF",
        b"%PDF-1.4\nTEXTLAYER:synthetic marker cannot become evidence",
    ],
)
def test_fake_markers_and_corrupt_inputs_are_not_text_layers(content: bytes) -> None:
    result = parse_pdf_text_layer(content)
    assert result.status == "unparseable" and result.normalized_text == ""


def test_page_limit_rejects_whole_oversize_document_without_truncation_as_success() -> None:
    result = parse_pdf_text_layer(make_pdf((None,) * 301))
    assert result.status == "unparseable"
    assert any("limit" in note for note in result.notes)


def test_nested_json_leaf_paths_follow_rfc6901_and_roundtrip_unicode() -> None:
    outcome = parse_json_document('{"a/b":{"~name":[{"文":"中文 value"}]}}'.encode())
    assert outcome.status == "parsed"
    assert outcome.blocks[0].block_type == "field:/a~1b/~0name/0/文"
    span = locate_evidence_span(outcome.blocks, "中文 value", block_id=outcome.blocks[0].block_id)
    assert outcome.normalized_text[span.start_offset : span.end_offset] == "中文 value"
    assert outcome.parser_version == "json-2.0.0"


@pytest.mark.parametrize(
    "content",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b"\xff",
        b"[" * 34 + b"0" + b"]" * 34,
    ],
)
def test_json_rejects_ambiguous_nonfinite_or_excessively_deep_inputs(content: bytes) -> None:
    result = parse_json_document(content)
    assert result.status == "unparseable" and not result.blocks


def test_native_pdf_process_memory_limit_is_effective() -> None:
    import os
    import subprocess
    import sys

    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "PYTHONPATH", "TEMP", "TMP"}
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from ai_intel.ingestion.parsing._pdf_worker import _bound_memory; "
            "handle = _bound_memory(); allocation = bytearray(600 * 1024 * 1024)",
        ],
        capture_output=True,
        env=environment,
        timeout=10,
    )
    assert result.returncode != 0
    assert b"MemoryError" in result.stderr or result.returncode < 0


def test_worker_extracts_saved_pages_without_ocr_or_password_guessing() -> None:
    from ai_intel.ingestion.parsing._pdf_worker import extract_pages

    assert extract_pages(make_pdf(("safe evidence",))) == {
        "pages": [{"page_number": 1, "text": "safe evidence"}],
        "notes": [],
    }
    assert extract_pages(make_pdf(("secret text",), encrypted=True))["pages"] == []
    assert extract_pages(make_pdf((None,)))["pages"] == []
    assert extract_pages(make_pdf((None,) * 301))["pages"] == []


def test_json_number_overflow_is_not_serialized_as_infinity() -> None:
    assert parse_json_document(b'{"x":1e999}').status == "unparseable"


def test_worker_text_limit_preserves_partial_pages_and_does_not_report_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ai_intel.ingestion.parsing import _pdf_worker

    monkeypatch.setattr(_pdf_worker, "MAX_TEXT_CHARACTERS", 10)
    result = _pdf_worker.extract_pages(make_pdf(("short", "longer text here")))
    assert result["pages"] == [{"page_number": 1, "text": "short"}]
    assert result["notes"] == ["pdf text limit exceeded"]


def test_pdf_parser_capacity_and_input_limits_are_explicit() -> None:
    from ai_intel.ingestion.parsing import pdf_text

    assert parse_pdf_text_layer(b"%PDF-1.4" + b"x" * pdf_text.MAX_PDF_BYTES).notes == (
        "pdf input limit exceeded",
    )
    assert pdf_text._PDF_CAPACITY.acquire(blocking=False)
    assert pdf_text._PDF_CAPACITY.acquire(blocking=False)
    try:
        assert parse_pdf_text_layer(b"%PDF-1.4").notes == ("pdf parser capacity reached",)
    finally:
        pdf_text._PDF_CAPACITY.release()
        pdf_text._PDF_CAPACITY.release()


def test_json_string_evidence_keeps_newlines_quotes_backslashes_and_non_bmp() -> None:
    import json

    quote = '中文\n版本 "1.2" 路径 C:\\app 😀'
    outcome = parse_json_document(json.dumps({"description": quote}).encode())
    assert outcome.status == "parsed"
    span = locate_evidence_span(outcome.blocks, quote, block_id=outcome.blocks[0].block_id)
    assert outcome.normalized_text[span.start_offset : span.end_offset] == quote
    assert outcome.normalized_text.encode("utf-8").decode() == outcome.normalized_text


@pytest.mark.parametrize(
    "content",
    [
        b'{"description":"\\ud800"}',
        b'{"description":"\\udfff"}',
        b'{"\\ud800":"value"}',
        b'{"description":"\\u0000"}',
        b'{"\\u0000":"value"}',
    ],
)
def test_json_rejects_text_that_cannot_be_saved_losslessly_in_pg_utf8(content: bytes) -> None:
    outcome = parse_json_document(content)
    assert outcome.status == "unparseable"
    assert not outcome.blocks


@pytest.mark.parametrize(
    "output",
    [
        b"broken-json",
        b"[]",
        b"{}",
        b'{"pages":[],"notes":[1]}',
        b'{"pages":[{"page_number":true,"text":"body"}],"notes":[]}',
        b'{"pages":[{"page_number":-1,"text":"body"}],"notes":[]}',
        b'{"pages":[{"page_number":1,"text":""}],"notes":[]}',
    ],
)
def test_corrupt_child_protocol_cannot_publish_text(
    monkeypatch: pytest.MonkeyPatch,
    output: bytes,
) -> None:
    from ai_intel.ingestion.parsing import pdf_text

    class ChildFixture:
        returncode = 0

        def communicate(self, content: bytes, timeout: int) -> tuple[bytes, None]:
            assert content.startswith(b"%PDF-") and timeout == 20
            return output, None

    monkeypatch.setattr(pdf_text.subprocess, "Popen", lambda *args, **kwargs: ChildFixture())
    outcome = parse_pdf_text_layer(b"%PDF-1.4")
    assert outcome.status == "unparseable"
    assert not outcome.blocks


def test_timeout_kills_child_and_releases_capacity_without_passing_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    from ai_intel.ingestion.parsing import pdf_text

    calls: list[str] = []

    class ChildFixture:
        def communicate(self, content: bytes | None = None, timeout: int | None = None):
            if content is not None:
                calls.append("initial")
                raise subprocess.TimeoutExpired("isolated-pdf-worker", 20)
            calls.append("drained")
            return b"", None

        def kill(self) -> None:
            calls.append("killed")

    def spawn(arguments, **options):
        assert arguments[-1] == "ai_intel.ingestion.parsing._pdf_worker"
        assert "R04_TEST_SECRET" not in options["env"]
        return ChildFixture()

    monkeypatch.setenv("R04_TEST_SECRET", "isolated-synthetic-provider-secret")
    monkeypatch.setattr(pdf_text.subprocess, "Popen", spawn)
    assert parse_pdf_text_layer(b"%PDF-1.4").notes == ("pdf extraction timed out",)
    assert calls == ["initial", "killed", "drained"]
    assert pdf_text._PDF_CAPACITY.acquire(blocking=False)
    assert pdf_text._PDF_CAPACITY.acquire(blocking=False)
    pdf_text._PDF_CAPACITY.release()
    pdf_text._PDF_CAPACITY.release()
