"""Real subprocess/spawn transports check failure and matching positive parent controls."""

from __future__ import annotations

import ctypes
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

from ai_intel.infrastructure import process_limits
from ai_intel.infrastructure.models import semantic
from ai_intel.ingestion.parsing import pdf_text

OUTPUT = Path(__file__).resolve().parent
RESULTS: list[dict[str, object]] = []


def apply_test_limit(hard_exit: bool) -> int | None:
    if hard_exit:
        process_limits._WINDOWS_CPU_GUARD_CODE = process_limits._WINDOWS_CPU_GUARD_CODE.replace(
            "    while True:\n",
            "    import time,os\n    time.sleep(0.4)\n    os._exit(99)\n    while True:\n",
        )
    return process_limits.bound_process_resources(memory_bytes=100 * 1024**2, cpu_seconds=1)


def semantic_fault_worker(connection, *arguments: object) -> None:
    handle = apply_test_limit(True)
    ctypes.PyDLL("kernel32").Sleep(2000)
    connection.send(("ok", [[1.0] + [0.0] * 383]))
    assert handle is not None


def semantic_control_worker(connection, *arguments: object) -> None:
    handle = apply_test_limit(False)
    ctypes.PyDLL("kernel32").Sleep(2000)
    connection.send(("ok", [[1.0] + [0.0] * 383]))
    assert handle is not None


def check_pdf(hard_exit: bool) -> None:
    original_popen = subprocess.Popen
    code = (
        "import ctypes\nfrom ai_intel.infrastructure import process_limits as limits\n"
        + (
            "limits._WINDOWS_CPU_GUARD_CODE=limits._WINDOWS_CPU_GUARD_CODE.replace("
            "'    while True:\\n','    import time,os\\n    time.sleep(0.4)\\n"
            "    os._exit(99)\\n    while True:\\n')\n"
            if hard_exit else ""
        )
        + "job=limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\n"
        "ctypes.PyDLL('kernel32').Sleep(2000)\n"
        "print('{\"pages\":[{\"page_number\":1,\"text\":\"BOUNDARY_CONTROL_TEXT\"}],"
        "\"notes\":[]}',flush=True)\n"
    )
    receipt: dict[str, object] = {}

    def launch_test_worker(command, **keywords):
        actual_command = [sys.executable, "-B", "-c", code]
        process = original_popen(actual_command, **keywords)
        receipt.update(command=actual_command, pid=process.pid)
        return process

    started = time.perf_counter()
    pdf_text.subprocess.Popen = launch_test_worker
    try:
        result = pdf_text.parse_pdf_text_layer(b"%PDF-1.7\n")
    finally:
        pdf_text.subprocess.Popen = original_popen
    receipt.update(name="pdf_fault" if hard_exit else "pdf_positive_control",
                   status=result.status, notes=result.notes,
                   wall_seconds=time.perf_counter() - started,
                   completed_at=datetime.now().astimezone().isoformat())
    RESULTS.append(receipt)
    if hard_exit:
        assert result.status == "unparseable"
        assert result.notes == ("invalid pdf parser output",)
    else:
        assert result.status == "parsed", (result.status, result.notes)
        assert any("BOUNDARY_CONTROL_TEXT" in block.text for block in result.blocks)


def check_semantic(hard_exit: bool) -> None:
    original_worker = semantic._semantic_worker
    semantic._semantic_worker = semantic_fault_worker if hard_exit else semantic_control_worker
    cache_directory = Path("D:/tmp/nativecpu-guard-review-1-recheck-20261015/parent-model-placeholder")
    cache_directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    receipt: dict[str, object] = {"name": "semantic_fault" if hard_exit else "semantic_positive_control",
                                "transport": "real multiprocessing spawn and Pipe; synthetic worker result"}
    try:
        result = semantic.LocalSemanticModels(cache_directory).embed_query("bounded")
        receipt.update(outcome="complete_result", dimensions=len(result.vectors[0]))
    except semantic.SemanticRuntimeError as error:
        receipt.update(outcome="rejected", error=str(error))
    finally:
        semantic._semantic_worker = original_worker
    receipt.update(wall_seconds=time.perf_counter() - started,
                   completed_at=datetime.now().astimezone().isoformat())
    RESULTS.append(receipt)
    if hard_exit:
        assert receipt["outcome"] == "rejected", receipt
        assert "exited without a result" in receipt["error"]
    else:
        assert receipt["outcome"] == "complete_result" and receipt["dimensions"] == 384, receipt


if __name__ == "__main__":
    try:
        for fault in (True, False):
            check_pdf(fault)
            check_semantic(fault)
    finally:
        (OUTPUT / "parent_boundary_results.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print(json.dumps({"checks": len(RESULTS), "results": RESULTS}), flush=True)
