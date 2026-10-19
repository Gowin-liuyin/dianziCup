"""有界PDF文本解析入口；原始内容只通过私有管道传给固定解析程序。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from threading import BoundedSemaphore

from ai_intel.ingestion.parsing.text_blocks import ParseOutcome, build_blocks_from_segments

PDF_PARSER_VERSION = "pdf-2.0.0"
MAX_PDF_BYTES = 32 * 1024 * 1024
WINDOWS_CREATE_NO_WINDOW = 0x08000000
_PDF_CAPACITY = BoundedSemaphore(2)


def _failure(note: str) -> ParseOutcome:
    return ParseOutcome(status="unparseable", notes=(note,), parser_version=PDF_PARSER_VERSION)


def parse_pdf_text_layer(content: bytes) -> ParseOutcome:
    """最多32MiB/300页/100万字符/20秒/512MiB；未抽取页保留partial。"""
    if not content.startswith(b"%PDF-"):
        return _failure("not a pdf")
    if len(content) > MAX_PDF_BYTES:
        return _failure("pdf input limit exceeded")
    if not _PDF_CAPACITY.acquire(blocking=False):
        return _failure("pdf parser capacity reached")
    try:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper()
            in {
                "SYSTEMROOT",
                "WINDIR",
                "PATH",
                "PYTHONPATH",
                "TEMP",
                "TMP",
            }
        }
        environment.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-m", "ai_intel.ingestion.parsing._pdf_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            creationflags=WINDOWS_CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            output, _ = process.communicate(content, timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return _failure("pdf extraction timed out")
        if process.returncode != 0 or len(output) > 6_100_000:
            return _failure("pdf extraction process failed or exceeded resource limit")
        try:
            result = json.loads(output)
        except (ValueError, UnicodeError):
            return _failure("invalid pdf parser output")
        if not isinstance(result, dict):
            return _failure("invalid pdf parser output")
        pages, notes = result.get("pages"), result.get("notes")
        if not isinstance(pages, list) or not isinstance(notes, list):
            return _failure("invalid pdf parser output")
        if len(pages) > 300 or len(notes) > 301 or any(not isinstance(n, str) for n in notes):
            return _failure("invalid pdf parser output")
        segments: list[tuple[str, str, int | None]] = []
        for page in pages:
            if (
                not isinstance(page, dict)
                or type(page.get("page_number")) is not int
                or not isinstance(page.get("text"), str)
            ):
                return _failure("invalid pdf parser output")
            number, text = page["page_number"], page["text"]
            if not 1 <= number <= 300 or not text.strip():
                return _failure("invalid pdf parser output")
            segments.append(("paragraph", text, number))
        outcome = build_blocks_from_segments(segments, PDF_PARSER_VERSION)
        return replace(
            outcome, status="partial" if segments and notes else outcome.status, notes=tuple(notes)
        )
    except OSError:
        return _failure("pdf extraction process unavailable")
    finally:
        _PDF_CAPACITY.release()
