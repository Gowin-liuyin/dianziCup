"""Profile the original scanner only on the scanning thread; preserve red findings."""

from __future__ import annotations

import cProfile
import json
import os
import pstats
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="milliseconds")


def save(name: str, value: object) -> None:
    (RUN / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def child() -> int:
    sys.path.insert(0, str(ROOT))
    from scripts import security_scan

    started = now()
    tick = time.monotonic()
    classifications = security_scan.load_fixture_classifications(
        ROOT, ROOT / "reports/security/recovery_fixture_false_positives.json"
    )
    assert len(classifications) == 136
    save(
        "s2b_scan_started.json",
        {
            "started_at": started,
            "scan_started_at": now(),
            "classification_count": len(classifications),
            "status": "original_scan_running",
        },
    )
    profile = cProfile.Profile()
    findings = []
    error_class = None
    scanner_exit = 0
    profile.enable()
    try:
        findings = security_scan.scan_repository(ROOT, classifications)
        scanner_exit = int(
            any(finding.category not in security_scan.SAFE_CATEGORIES for finding in findings)
        )
    except (security_scan.ClassificationError, OSError) as error:
        error_class = type(error).__name__
        scanner_exit = 2
    finally:
        profile.disable()
        profile.dump_stats(str(RUN / "s2b_complete.pstats"))
        rows = []
        for (filename, line, function), stats in pstats.Stats(profile).stats.items():
            rows.append(
                {
                    "filename": filename,
                    "line": line,
                    "function": function,
                    "calls": stats[1],
                    "self_seconds": stats[2],
                    "cumulative_seconds": stats[3],
                }
            )
        rows.sort(key=lambda row: float(row["cumulative_seconds"]), reverse=True)
        save("s2b_profile.json", rows)
        totals = {
            row["function"]: row
            for row in rows
            if row["function"] in {"scan_repository", "_canonical_path", "read_bytes", "resolve"}
        }
        assert float(totals["scan_repository"]["cumulative_seconds"]) >= max(
            float(totals["_canonical_path"]["cumulative_seconds"]),
            float(totals["read_bytes"]["cumulative_seconds"]),
        )
        finding_metadata = [asdict(finding) for finding in findings]
        assert all(
            set(finding) == {"path", "pattern_id", "category"} for finding in finding_metadata
        )
        assert int(totals["_canonical_path"]["calls"]) == int(totals["read_bytes"]["calls"]) + sum(
            finding.pattern_id == "path_boundary" for finding in findings
        )
        receipt = {
            "started_at": started,
            "ended_at": now(),
            "duration_seconds": time.monotonic() - tick,
            "scanner_exit_code": scanner_exit,
            "error_class": error_class,
            "classification_count": len(classifications),
            "scan_function_totals": totals,
            "finding_category_counts": dict(Counter(finding.category for finding in findings)),
            "findings": finding_metadata,
            "exact_authorized_secret_scan": "not_run",
            "scanner_functions_replaced": False,
            "profile_thread_count": 1,
            "profile_consistency_assertions": "passed",
        }
        save("s2b_child_receipt.json", receipt)
        print(json.dumps(receipt), flush=True)
    return scanner_exit


def supervise() -> int:
    started = now()
    tick = time.monotonic()
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--child"]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    prefixes = (
        "GENERATION_",
        "DEEPSEEK_",
        "FOFA_",
        "HUNTER_",
        "QUAKE_",
        "ZOOMEYE_",
        "LANGSMITH_",
        "LANGCHAIN_",
    )
    for name in tuple(environment):
        if name.startswith(prefixes) or name == "TEST_DATABASE_URL":
            environment.pop(name)
    save(
        "s2b_started.json",
        {
            "started_at": started,
            "command": command,
            "cwd": str(ROOT),
            "maximum_seconds": 180,
        },
    )
    timed_out = False
    process = None
    try:
        with (RUN / "s2b.log").open("wb") as output:
            process = subprocess.Popen(
                command, cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT
            )
            next_progress = tick + 30
            while process.poll() is None:
                if time.monotonic() >= tick + 180:
                    timed_out = True
                    process.kill()
                    process.wait(timeout=5)
                    break
                if time.monotonic() >= next_progress:
                    progress = {
                        "observed_at": now(),
                        "elapsed_seconds": time.monotonic() - tick,
                        "owned_child_alive": True,
                        "child_pid": process.pid,
                        "scan_started_receipt_exists": (RUN / "s2b_scan_started.json").exists(),
                    }
                    save("s2b_progress.json", progress)
                    print(json.dumps(progress), flush=True)
                    next_progress += 30
                time.sleep(0.2)
    finally:
        child_exit = process.returncode if process is not None else None
        receipt = {
            "started_at": started,
            "ended_at": now(),
            "duration_seconds": time.monotonic() - tick,
            "maximum_seconds": 180,
            "command": command,
            "timed_out": timed_out,
            "child_exit_code": child_exit,
            "supervisor_exit_code": 124 if timed_out else child_exit,
            "owned_child_exited": process.poll() is not None if process is not None else True,
            "complete_profile_exists": (RUN / "s2b_complete.pstats").exists(),
        }
        save("s2b_supervisor_receipt.json", receipt)
        print(json.dumps(receipt), flush=True)
    return 124 if timed_out else int(child_exit or 0)


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        raise SystemExit(child())
    if len(sys.argv) == 1:
        raise SystemExit(supervise())
    raise SystemExit(2)
