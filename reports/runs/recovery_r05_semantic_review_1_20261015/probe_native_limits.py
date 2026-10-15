"""Probe only disposable native-limited children; never touch service processes."""

import argparse
import json
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("helper")
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    prefix = (
        "from ai_intel.ingestion.parsing._pdf_worker import _bound_memory\n"
        "handle = _bound_memory()\n"
        if args.pdf else
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('probe_limit', {args.helper!r})\n"
        "helper = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(helper)\n"
    )
    probes = [("pdf_cpu", "print('LIMIT_APPLIED',flush=True)\nwhile True:\n    pass\n", 30)] if args.pdf else [
        ("memory", "handle=helper.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=5)\n"
         "print('LIMIT_APPLIED',flush=True)\nallocation=bytearray(200*1024**2)\n"
         "print('UNEXPECTED_ALLOCATION',flush=True)\n", 8),
        ("cpu", "handle=helper.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\n"
         "print('LIMIT_APPLIED',flush=True)\nwhile True:\n    pass\n", 15),
    ]
    for name, code, deadline in probes:
        started = time.monotonic()
        result = subprocess.run([sys.executable, "-c", prefix + code], capture_output=True,
                                timeout=deadline, check=False)
        elapsed = time.monotonic() - started
        print(json.dumps({"probe": name, "python": sys.version, "returncode": result.returncode,
                          "seconds": elapsed, "stdout": result.stdout.decode(errors="replace"),
                          "stderr": result.stderr.decode(errors="replace")}))
        assert b"LIMIT_APPLIED" in result.stdout
        assert b"UNEXPECTED_ALLOCATION" not in result.stdout
        assert result.returncode != 0
        if name.endswith("cpu"):
            assert b"Traceback" not in result.stderr
        else:
            assert b"MemoryError" in result.stderr or result.returncode < 0


if __name__ == "__main__":
    main()
