"""只从stdin读取PDF，在独立限额进程中抽取文本，不执行附件或外部程序。"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import sys
from io import BytesIO

from pypdf import PdfReader, overwrite_configuration
from pypdf.errors import PyPdfError

MAX_PDF_BYTES = 32 * 1024 * 1024
MAX_PDF_PAGES = 300
MAX_TEXT_CHARACTERS = 1_000_000
MAX_MEMORY_BYTES = 512 * 1024 * 1024


def _bound_memory() -> int | None:
    """Linux使用进程地址空间限额，Windows使用进程Job硬内存限额。"""
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        return None

    if os.name != "nt":
        raise OSError("pdf resource limit unavailable")

    from ctypes import wintypes

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "read_operations",
                "write_operations",
                "other_operations",
                "read_bytes",
                "write_bytes",
                "other_bytes",
            )
        ]

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("minimum_working_set", ctypes.c_size_t),
            ("maximum_working_set", ctypes.c_size_t),
            ("active_processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", BasicLimits),
            ("io", IoCounters),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if handle is None:
        raise OSError("pdf resource limit unavailable")
    limits = ExtendedLimits()
    limits.basic.flags = 0x100 | 0x2000
    limits.process_memory = MAX_MEMORY_BYTES
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        kernel.CloseHandle(handle)
        raise OSError("pdf resource limit unavailable")
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        kernel.CloseHandle(handle)
        raise OSError("pdf resource limit unavailable")
    return int(handle)


def extract_pages(content: bytes) -> dict[str, object]:
    """页码按原PDF从1开始；缺少文本只记录缺口，不推断为扫描件。"""
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
