"""Read existing connection evidence without importing business code or connecting to services."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
REVIEW_ROOT = Path("D:/wt/batch13-default-product-review1")
ORIGINAL = REVIEW_ROOT / "reports/runs/batch13_default_product_review1_20261017"
SOURCE_SHA = "bc089809c03472582f6256b495a6f9a2a308a5d2"
SHANGHAI = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(UTC).astimezone(SHANGHAI).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_receipt(path: Path) -> dict:
    receipt = read_json(path)
    return {
        "path": str(path),
        "sha256": file_hash(path),
        "source_sha": receipt["source_sha"],
        "started_at": receipt["started_at"],
        "ended_at": receipt["ended_at"],
        "exit_code": receipt["exit_code"],
        "controller_identity": receipt["control_chain"][0],
        "connection_peak": receipt["actual_psycopg_connection_peak"],
        "target_connections_after_explicit_shutdown": receipt[
            "own_pg_connections_after_shutdown"
        ],
        "database_drop_verified": receipt["owned_database_drop_verified"],
        "windows_observed_peak": receipt["windows_peak_count"],
        "remaining_owned_processes": receipt["remaining_owned_processes"],
    }


started = now()
monotonic_start = time.monotonic()
spec = importlib.util.spec_from_file_location(
    "existing_review_identity", ORIGINAL / "batch13_process_metadata.py"
)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)
control, chain = metadata.control_root(metadata.current_identity())
peak = metadata.descendants(control)
stop = threading.Event()
sampling_failure = []


def sample_owned_tree() -> None:
    global peak
    while not stop.wait(0.025):
        try:
            current = metadata.descendants(control)
            if len(current) > len(peak):
                peak = current
            if len(current) > 8:
                sampling_failure.append("owned_process_cap_exceeded")
                return
        except OSError as error:
            sampling_failure.append(type(error).__name__)
            return


sampler = threading.Thread(
    target=sample_owned_tree, name="existing-method-diagnosis-process-sampler"
)
sampler.start()
failure = None
try:
    first = summarize_receipt(ORIGINAL / "product_receipt.json")
    second = summarize_receipt(ORIGINAL / "supplement/product_receipt.json")
    resume = summarize_receipt(ORIGINAL / "supplement/resume_receipt.json")
    manifest = read_json(ORIGINAL / "source_before.json")
    expected = {entry["path"]: entry["raw_sha256"] for entry in manifest["files"]}
    source_paths = [
        "backend/migrations/env.py",
        "backend/src/ai_intel/infrastructure/database.py",
        "backend/src/ai_intel/api/app.py",
        "backend/src/ai_intel/workers/investigation.py",
        "backend/src/ai_intel/investigation/runtime.py",
        "backend/src/ai_intel/investigation/workflow_service.py",
        "backend/src/ai_intel/investigation/checkpoint_runtime.py",
    ]
    sources = []
    for relative in source_paths:
        actual = file_hash(REVIEW_ROOT / relative)
        sources.append(
            {
                "path": relative,
                "raw_sha256": actual,
                "frozen_sha256": expected[relative],
                "matches": actual == expected[relative],
            }
        )
    original_paths = [
        "product.py",
        "supplement_product.py",
        "resume_product.py",
        "resource_guard_failure.json",
        "supplement/resource_guard_failure.json",
        "cleanup_receipt.json",
        "default_factory.json",
        "supplement/default_factory.json",
        "source_before.json",
        "source_after.json",
        "raw_archive_receipt.json",
        "index_attempt2/index.stdout.log",
        "index_trace/supplement/worker_execute.stdout.log",
    ]
    evidence = {
        "recorded_at": now(),
        "source_sha": SOURCE_SHA,
        "source_tree_sha256": manifest["tree_sha256"],
        "source_python_file_count": manifest["python_file_count"],
        "first": first,
        "second": second,
        "resume": resume,
        "first_guard": read_json(ORIGINAL / "resource_guard_failure.json"),
        "current_supplement_guard": read_json(
            ORIGINAL / "supplement/resource_guard_failure.json"
        ),
        "first_post_exit_cleanup": read_json(ORIGINAL / "cleanup_receipt.json"),
        "source_files": sources,
        "original_hashes": [
            {"path": str(ORIGINAL / relative), "sha256": file_hash(ORIGINAL / relative)}
            for relative in original_paths
        ],
        "business_tests_run": 0,
        "database_connections_created": 0,
        "backend_identity_samples_available": False,
        "second_original_guard_separate_file_available": False,
    }
    (RUN / "safe_evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
except (OSError, ValueError, KeyError, TypeError) as error:
    failure = type(error).__name__
finally:
    stop.set()
    sampler.join(timeout=2)
    current = metadata.descendants(control)
    if len(current) > len(peak):
        peak = current
    receipt = {
        "command": [sys.executable, str(Path(__file__).resolve())],
        "cwd": str(Path.cwd()),
        "started_at": started,
        "ended_at": now(),
        "elapsed_seconds": time.monotonic() - monotonic_start,
        "exit_code": int(failure is not None or bool(sampling_failure)),
        "failure": failure,
        "sampling_failure": sampling_failure,
        "owned_cap": 8,
        "windows_observed_peak_count": len(peak),
        "windows_observed_peak_chain": list(peak.values()),
        "control_chain": chain,
        "timeout_seconds": 55,
        "business_tests_run": 0,
        "database_connections_created": 0,
    }
    (RUN / "extract_safe_evidence.command.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
print(
    json.dumps(
        {
            "exit_code": receipt["exit_code"],
            "windows_observed_peak_count": len(peak),
            "elapsed_seconds": receipt["elapsed_seconds"],
            "failure": failure,
        }
    )
)
raise SystemExit(receipt["exit_code"])
