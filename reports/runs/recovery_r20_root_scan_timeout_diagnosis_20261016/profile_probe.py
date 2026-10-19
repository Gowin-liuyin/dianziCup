"""Run approved bounded original-scanner diagnosis with metadata-only output."""

from __future__ import annotations

import cProfile
import json
import marshal
import os
import pstats
import subprocess
import sys
import threading
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
TABLE = ROOT / "reports/security/recovery_fixture_false_positives.json"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="milliseconds")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def profile_summary(profile: cProfile.Profile) -> list[dict[str, object]]:
    profile.snapshot_stats()
    result = []
    for (filename, line, function), stats in pstats.Stats(profile).stats.items():
        primitive_calls, total_calls, self_seconds, cumulative_seconds, _ = stats
        result.append(
            {
                "filename": filename,
                "line": line,
                "function": function,
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "self_seconds": self_seconds,
                "cumulative_seconds": cumulative_seconds,
            }
        )
    return sorted(result, key=lambda row: float(row["cumulative_seconds"]), reverse=True)


def checkpoint(profile: cProfile.Profile, mode: str, started: str, tick: float) -> None:
    profile.snapshot_stats()
    with (RUN / f"{mode}_partial.pstats").open("wb") as output:
        marshal.dump(profile.stats, output)
    counts = Counter()
    for (_, _, function), stats in profile.stats.items():
        if function in {"_canonical_path", "read_bytes", "scan_repository", "resolve"}:
            counts[function] += stats[1]
    progress = {
        "started_at": started,
        "observed_at": now(),
        "elapsed_seconds": time.monotonic() - tick,
        "completed_or_entered_function_call_counts": dict(counts),
        "status": "running",
    }
    write_json(RUN / f"{mode}_progress.json", progress)
    print(json.dumps(progress), flush=True)


def child(mode: str) -> int:
    sys.path.insert(0, str(ROOT))
    from scripts import security_scan

    started = now()
    tick = time.monotonic()
    profile = cProfile.Profile()
    finish = threading.Event()
    selected = []
    findings = []
    error_class = None
    exit_code = 0
    if mode == "s1":
        allocations = (48, 8, 48, 2, 150)
        for relative_root, allocation in zip(security_scan.SCAN_ROOTS, allocations, strict=True):
            paths = [
                path.relative_to(ROOT).as_posix()
                for path in sorted((ROOT / relative_root).rglob("*"))
                if path.is_file() and path.suffix in security_scan.SCAN_SUFFIXES
            ]
            count = min(allocation, len(paths))
            if count == 1:
                selected.extend(paths[:1])
            elif count > 1:
                selected.extend(
                    paths[index * (len(paths) - 1) // (count - 1)] for index in range(count)
                )
        assert 0 < len(selected) <= 256
        assert len(selected) == len(set(selected))
        classifications = ()
    else:
        classifications = security_scan.load_fixture_classifications(ROOT, TABLE)
        assert len(classifications) == 136

    def progress_worker() -> None:
        while not finish.wait(30):
            checkpoint(profile, mode, started, tick)

    worker = threading.Thread(target=progress_worker, daemon=True)
    worker.start()
    profile.enable()
    try:
        if mode == "s1":
            for relative_path in selected:
                security_scan._canonical_path(ROOT, relative_path)
        else:
            findings = security_scan.scan_repository(ROOT, classifications)
            exit_code = int(
                any(finding.category not in security_scan.SAFE_CATEGORIES for finding in findings)
            )
    except (security_scan.ClassificationError, OSError) as error:
        error_class = type(error).__name__
        exit_code = 2
    finally:
        profile.disable()
        finish.set()
        worker.join(timeout=2)
        profile.dump_stats(str(RUN / f"{mode}_complete.pstats"))
        summary = profile_summary(profile)
        write_json(RUN / f"{mode}_profile.json", summary)
        finding_metadata = [asdict(finding) for finding in findings]
        assert all(
            set(finding) == {"path", "pattern_id", "category"} for finding in finding_metadata
        )
        if mode == "s1":
            calls = sum(
                int(row["total_calls"]) for row in summary if row["function"] == "_canonical_path"
            )
            assert calls == len(selected)
        receipt = {
            "mode": mode,
            "started_at": started,
            "ended_at": now(),
            "duration_seconds": time.monotonic() - tick,
            "exit_code": exit_code,
            "error_class": error_class,
            "selected_metadata_only_paths": selected,
            "full_original_scan": mode == "s2",
            "original_roots": security_scan.SCAN_ROOTS,
            "original_suffixes": sorted(security_scan.SCAN_SUFFIXES),
            "findings": finding_metadata,
            "finding_category_counts": dict(Counter(finding.category for finding in findings)),
            "classification_count": len(classifications),
            "exact_authorized_secret_scan": "not_run",
            "scanner_functions_replaced": False,
            "profile_top_cumulative": summary[:30],
        }
        write_json(RUN / f"{mode}_child_receipt.json", receipt)
        print(
            json.dumps(
                {key: value for key, value in receipt.items() if key != "profile_top_cumulative"}
            ),
            flush=True,
        )
    return exit_code


def supervise(mode: str) -> int:
    maximum_seconds = 30 if mode == "s1" else 180
    started = now()
    tick = time.monotonic()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    for name in tuple(environment):
        if (
            name.startswith(
                (
                    "GENERATION_",
                    "DEEPSEEK_",
                    "FOFA_",
                    "HUNTER_",
                    "QUAKE_",
                    "ZOOMEYE_",
                    "LANGSMITH_",
                    "LANGCHAIN_",
                )
            )
            or name == "TEST_DATABASE_URL"
        ):
            environment.pop(name)
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--child", mode]
    write_json(
        RUN / f"{mode}_started.json",
        {
            "started_at": started,
            "command": command,
            "cwd": str(ROOT),
            "maximum_seconds": maximum_seconds,
            "approval": (
                "Root approved S1 <=256 metadata paths / 30s and S2 once original scan / 180s"
            ),
        },
    )
    timed_out = False
    process = None
    try:
        with (RUN / f"{mode}.log").open("wb") as output:
            process = subprocess.Popen(
                command, cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT
            )
            deadline = tick + maximum_seconds
            next_progress = tick + 30
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    timed_out = True
                    process.kill()
                    process.wait(timeout=5)
                    break
                if time.monotonic() >= next_progress:
                    progress_path = RUN / f"{mode}_progress.json"
                    progress = (
                        json.loads(progress_path.read_text(encoding="utf-8"))
                        if progress_path.exists()
                        else {"status": "no_child_checkpoint_yet"}
                    )
                    print(
                        json.dumps(
                            {"parent_observed_at": now(), "mode": mode, "child_progress": progress}
                        ),
                        flush=True,
                    )
                    next_progress += 30
                time.sleep(0.2)
    finally:
        child_exit = process.returncode if process is not None else None
        receipt = {
            "started_at": started,
            "ended_at": now(),
            "duration_seconds": time.monotonic() - tick,
            "mode": mode,
            "command": command,
            "cwd": str(ROOT),
            "maximum_seconds": maximum_seconds,
            "timed_out": timed_out,
            "child_exit_code": child_exit,
            "supervisor_exit_code": 124 if timed_out else child_exit,
            "child_pid": process.pid if process is not None else None,
            "owned_child_exited": process.poll() is not None if process is not None else True,
            "child_stdout_direct_to_log": True,
            "partial_profile_exists": (RUN / f"{mode}_partial.pstats").exists(),
            "complete_profile_exists": (RUN / f"{mode}_complete.pstats").exists(),
        }
        write_json(RUN / f"{mode}_supervisor_receipt.json", receipt)
        print(json.dumps(receipt), flush=True)
    return 124 if timed_out else int(child_exit or 0)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child" and sys.argv[2] in {"s1", "s2"}:
        raise SystemExit(child(sys.argv[2]))
    if len(sys.argv) == 2 and sys.argv[1] in {"s1", "s2"}:
        raise SystemExit(supervise(sys.argv[1]))
    raise SystemExit(2)
