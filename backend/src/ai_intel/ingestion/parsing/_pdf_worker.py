"""只从stdin读取PDF，在独立限额进程中抽取文本，不执行附件或外部程序。"""

from __future__ import annotations

import json
import logging
import sys
from io import BytesIO

from ai_intel.infrastructure.process_limits import bound_process_resources

MAX_PDF_BYTES = 32 * 1024 * 1024
MAX_PDF_PAGES = 300
MAX_TEXT_CHARACTERS = 1_000_000
MAX_MEMORY_BYTES = 512 * 1024 * 1024


def _bound_memory() -> int | None:
    """Keep the parser envelope while sharing the native process limiter."""
    return bound_process_resources(memory_bytes=MAX_MEMORY_BYTES, cpu_seconds=15)


def extract_pages(content: bytes) -> dict[str, object]:
    """页码按原PDF从1开始；缺少文本只记录缺口，不推断为扫描件。"""
    from pypdf import PdfReader, overwrite_configuration
    from pypdf.errors import PyPdfError

    overwrite_configuration(
        maximum_declared_stream_length=8 * 1024 * 1024,
        array_based_stream_maximum_output_length=8 * 1024 * 1024,
        zlib_maximum_output_length=8 * 1024 * 1024,
        lzw_maximum_output_length=8 * 1024 * 1024,
        run_length_maximum_output_length=8 * 1024 * 1024,
        brotli_maximum_output_length=8 * 1024 * 1024,
        stream_decoding_work_maximum_length=32 * 1024 * 1024,
        page_tree_maximum_entries=MAX_PDF_PAGES + 1,
        page_tree_maximum_depth=32,
        xform_maximum_invocations_per_extraction=100,
        jbig2dec_binary=None,
    )
    reader = PdfReader(BytesIO(content), strict=True)
    if reader.is_encrypted:
        return {"pages": [], "notes": ["encrypted pdf requires authorized decryption"]}
    if len(reader.pages) > MAX_PDF_PAGES:
        return {"pages": [], "notes": ["pdf page limit exceeded"]}
    pages: list[dict[str, object]] = []
    notes: list[str] = []
    characters = 0
    for number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text().strip()
        except (PyPdfError, ValueError, KeyError, TypeError, RecursionError):
            notes.append(f"page {number}: text extraction failed")
            continue
        if not text:
            notes.append(f"page {number}: no reliable text layer; OCR not performed")
            continue
        characters += len(text)
        if characters > MAX_TEXT_CHARACTERS:
            notes.append("pdf text limit exceeded")
            break
        pages.append({"page_number": number, "text": text})
    return {"pages": pages, "notes": notes}


def main() -> None:
    """固定JSON输出避免把PDF、路径或库异常回显给父进程。"""
    logging.disable(logging.CRITICAL)
    try:
        memory_handle = _bound_memory()
    except OSError:
        result: dict[str, object] = {"pages": [], "notes": ["pdf resource limit unavailable"]}
    else:
        from pypdf.errors import PyPdfError

        content = sys.stdin.buffer.read(MAX_PDF_BYTES + 1)
        try:
            result = (
                extract_pages(content)
                if len(content) <= MAX_PDF_BYTES
                else {
                    "pages": [],
                    "notes": ["pdf input limit exceeded"],
                }
            )
        except (PyPdfError, ValueError, KeyError, TypeError, RecursionError, MemoryError):
            result = {"pages": [], "notes": ["invalid or resource-limited pdf"]}
        del memory_handle
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
