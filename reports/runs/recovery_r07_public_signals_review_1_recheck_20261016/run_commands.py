"""Record independent fixed-candidate rechecks without changing business files."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"
MATERIAL = "facf6cce653de318ac966e71ac62b479e562aa61"
CODE = "9df5a61d29ff489e13fb87876e35399ebb9cb00a"
SOURCE_PATHS = (
    "backend/src/ai_intel/enrichment/signals.py",
    "backend/src/ai_intel/enrichment/signal_sources.py",
    "backend/tests/unit/test_r07_public_signals.py",
    "backend/tests/contract/test_r07_public_signal_sources.py",
    "backend/tests/unit/test_r07_public_signals_fix1.py",
    "backend/tests/contract/test_r07_public_signals_fix1_cwe.py",
    "backend/src/ai_intel/enrichment/contracts.py",
    "backend/src/ai_intel/domain/enrichment_values.py",
)


def timestamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def hashes():
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}


def run(name, argv, cwd=BACKEND, timeout=60):
    before = hashes()
    started = timestamp()
    with (RUN / f"{name}.log").open("w", encoding="utf-8") as stream:
        completed = subprocess.run(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=timeout, check=False)
    receipt = {"name": name, "started_at": started, "ended_at": timestamp(), "argv": argv,
               "cwd": str(cwd), "exit_code": completed.returncode,
               "candidate_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "code_sha": CODE, "source_hashes_before": before, "source_hashes_after": hashes(),
               "source_hashes_unchanged": before == hashes(), "new_network_calls": 0, "new_model_calls": 0,
               "pg_calls": 0, "script_input_hashes": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                   for value in argv for path in [Path(value)] if path.is_file() and path.suffix == ".py"}}
    (RUN / f"{name}.command.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("name", "started_at", "ended_at", "exit_code")}))
    print((RUN / f"{name}.log").read_text(encoding="utf-8"))
    return completed.returncode


if __name__ == "__main__":
    action = sys.argv[1]
    static_files = [path.removeprefix("backend/") for path in SOURCE_PATHS[:6]]
    tests = {
        "focused": static_files[2:4],
        "new_regression": static_files[4:6],
        "original_triggers": [str(RUN / "test_independent_boundaries.py"), "-k",
                              "same_cve_nvd_vendor_different_scores_must_conflict or unrelated_valid_cwe_selection_does_not_remove_verified_candidate"],
        "independent_all": [str(RUN / "test_independent_boundaries.py")],
        "regression": ["tests/unit/test_r04_nvd_actual_schema.py", "tests/unit/test_r04_vendor_advisories.py",
                       "tests/unit/test_r04_vendor_missing_package.py", "tests/unit/test_t19_structured_enrichment.py",
                       "tests/contract/test_t10_cve_nvd_connectors.py", "tests/contract/test_t12_vendor_blog_connectors.py",
                       "tests/contract/test_t23_poc_scores_impact.py"],
    }
    if action in tests:
        command = [str(PYTHON), "-m", "pytest", *tests[action], "--no-cov", "-q",
                   f"--junitxml={RUN / (action + '.xml')}"]
    else:
        commands = {
            "sync": ["C:/Users/yinha/.local/bin/uv.exe", "sync", "--offline", "--frozen"],
            "ruff": [str(PYTHON), "-m", "ruff", "check", *static_files],
            "format": [str(PYTHON), "-m", "ruff", "format", "--check", *static_files],
            "mypy": [str(PYTHON), "-m", "mypy", *static_files[:2]],
            "recorded_public_replay": [str(PYTHON), str(RUN / "replay_public_bodies.py")],
        }
        command = commands[action]
    raise SystemExit(run(action, command))
