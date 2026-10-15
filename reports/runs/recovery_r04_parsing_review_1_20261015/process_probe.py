"""Exercise process failure, fail-closed limits, and actual parent timeout cleanup."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from ai_intel.ingestion.parsing import pdf_text


def main() -> None:
    original_popen = subprocess.Popen
    processes: list[subprocess.Popen[bytes]] = []
    checks: list[dict[str, object]] = []

    def substitute(code: str):
        def create(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            process = original_popen([sys.executable, "-c", code], **kwargs)
            processes.append(process)
            return process
        return create

    for name, code, note in [
        ("nonzero_exit", "raise SystemExit(7)", "pdf extraction process failed or exceeded resource limit"),
        ("invalid_protocol", "print('this is not JSON')", "invalid pdf parser output"),
        ("wrong_protocol_shape", "print('[1, 2]')", "invalid pdf parser output"),
        ("invalid_page_number", "print('{\"pages\":[{\"page_number\":0,\"text\":\"test\"}],\"notes\":[]}')", "invalid pdf parser output"),
        ("timeout", "import time; time.sleep(60)", "pdf extraction timed out"),
    ]:
        start = time.monotonic()
        with patch.object(pdf_text.subprocess, "Popen", substitute(code)):
            result = pdf_text.parse_pdf_text_layer(b"%PDF-1.7\nreview-input-not-valid-content")
        elapsed = time.monotonic() - start
        passed = result.status == "unparseable" and result.notes == (note,) and processes[-1].poll() is not None
        if name == "timeout":
            passed = passed and 19 <= elapsed <= 25
        checks.append({"name": name, "passed": passed, "status": result.status, "notes": result.notes, "elapsed_seconds": elapsed, "child_reaped": processes[-1].poll() is not None})
    code = "from ai_intel.ingestion.parsing import _pdf_worker\ndef unavailable():\n raise OSError('synthetic-limit-unavailable')\n_pdf_worker._bound_memory=unavailable\n_pdf_worker.main()"
    fail_closed = subprocess.run([sys.executable, "-c", code], input=b"%PDF-1.7", capture_output=True, timeout=10, check=False)
    payload = json.loads(fail_closed.stdout)
    checks.append({"name": "limit_unavailable_fail_closed", "passed": fail_closed.returncode == 0 and payload == {"pages": [], "notes": ["pdf resource limit unavailable"]}, "payload": payload, "returncode": fail_closed.returncode})
    marker = b"synthetic-private-content-marker-not-a-secret"
    real_error = pdf_text.parse_pdf_text_layer(b"%PDF-1.7\n" + marker)
    checks.append({"name": "malformed_pdf_does_not_echo_input", "passed": real_error.status == "unparseable" and marker.decode() not in json.dumps(real_error.notes), "notes": real_error.notes})
    acquired = [pdf_text._PDF_CAPACITY.acquire(blocking=False), pdf_text._PDF_CAPACITY.acquire(blocking=False)]
    checks.append({"name": "semaphore_released_after_all_failures", "passed": acquired == [True, True], "acquired": acquired})
    for held in acquired:
        if held:
            pdf_text._PDF_CAPACITY.release()
    result = {"passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks), "checks": checks}
    Path(__file__).with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["failed"] else 0)


if __name__ == "__main__":
    main()
