"""Record bounded checks with real local timestamps; fixture checks are never labeled live."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
BACKEND = WORKTREE / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"


def execute(name: str, arguments: list[str], timeout: int = 240) -> int:
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    sources = (BACKEND / "src/ai_intel/enrichment/signals.py",
               BACKEND / "src/ai_intel/enrichment/signal_sources.py",
               BACKEND / "tests/unit/test_r07_public_signals.py",
               BACKEND / "tests/contract/test_r07_public_signal_sources.py")
    before_hashes = {str(path.relative_to(WORKTREE)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sources}
    before_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip()
    with (RUN / (name + ".log")).open("w", encoding="utf-8") as stream:
        result = subprocess.run(arguments, cwd=BACKEND, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    ended = datetime.now().astimezone().isoformat(timespec="seconds")
    receipt = {"name": name, "cwd": str(BACKEND), "argv": arguments, "started_at": started,
               "ended_at": ended, "exit_code": result.returncode,
               "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip(),
               "before_head": before_head, "input_hashes_before": before_hashes,
               "input_hashes": {str(path.relative_to(WORKTREE)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sources}}
    receipt["source_hashes_unchanged"] = receipt["input_hashes"] == before_hashes
    (RUN / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(name, result.returncode, flush=True)
    return result.returncode


if __name__ == "__main__":
    mode = sys.argv[1]
    targets = ["src/ai_intel/enrichment/signals.py", "src/ai_intel/enrichment/signal_sources.py",
               "tests/unit/test_r07_public_signals.py", "tests/contract/test_r07_public_signal_sources.py"]
    commands = {
        "focused": [str(PYTHON), "-m", "pytest", "tests/unit/test_r07_public_signals.py",
                    "tests/contract/test_r07_public_signal_sources.py", "--no-cov", "-q",
                    "--junitxml=" + str(RUN / "focused.xml")],
        "ruff": [str(PYTHON), "-m", "ruff", "check", *targets],
        "format": [str(PYTHON), "-m", "ruff", "format", "--check", *targets],
        "mypy": [str(PYTHON), "-m", "mypy", *targets[:2]],
        "pure": [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract", "-q",
                 "--junitxml=" + str(RUN / "pure.xml")],
        "pure_corrected": [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract",
                           "tests/security", "-m", "not real_pg", "-q",
                           "--junitxml=" + str(RUN / "pure_corrected.xml")],
    }
    commands["native_frozen"] = [str(PYTHON), "-m", "pytest",
        "tests/unit/test_r20_native_cpu_guard.py::test_real_product_worker_starts_guard_and_job_cleans_it_on_exit[pdf]",
        "--no-cov", "-q", "--junitxml=" + str(RUN / "native_frozen.xml")]
    for base in ("focused", "ruff", "format", "mypy"):
        commands[base + "_frozen"] = [argument.replace(base + ".xml", base + "_frozen.xml")
                                     for argument in commands[base]]
    commands["pure_frozen"] = [argument.replace("pure_corrected.xml", "pure_frozen.xml")
                               for argument in commands["pure_corrected"]]
    raise SystemExit(execute(mode, commands[mode]))
