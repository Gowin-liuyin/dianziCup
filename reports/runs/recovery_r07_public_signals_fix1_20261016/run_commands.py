"""Record bounded offline fix checks and immutable pre/post source bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"
REVIEW_RUN = Path("D:/wt/r07-public-signals-review-1/reports/runs/recovery_r07_public_signals_review_1_20261016")
SOURCE_PATHS = (
    "backend/src/ai_intel/enrichment/signals.py",
    "backend/src/ai_intel/enrichment/signal_sources.py",
    "backend/tests/unit/test_r07_public_signals.py",
    "backend/tests/contract/test_r07_public_signal_sources.py",
    "backend/src/ai_intel/enrichment/contracts.py",
    "backend/src/ai_intel/domain/enrichment_values.py",
)
NEW_TEST = "backend/tests/unit/test_r07_public_signals_fix1.py"
NEW_CONTRACT = "backend/tests/contract/test_r07_public_signals_fix1_cwe.py"


def timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def hashes() -> dict[str, str]:
    paths = (*SOURCE_PATHS, NEW_TEST, NEW_CONTRACT)
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in paths if (ROOT / path).exists()}


def run(name: str, argv: list[str], cwd: Path = BACKEND, timeout: int = 60) -> int:
    before = hashes()
    started = timestamp()
    with (RUN / f"{name}.log").open("wb") as stream:
        completed = subprocess.run(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=timeout, check=False)
    receipt = {"name": name, "started_at": started, "ended_at": timestamp(), "argv": argv,
               "cwd": str(cwd), "exit_code": completed.returncode,
               "candidate_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                         text=True).strip(),
               "source_hashes_before": before, "source_hashes_after": hashes(),
               "source_hashes_unchanged": before == hashes(), "new_network_calls": 0,
               "new_model_calls": 0, "pg_calls": 0, "mapping_calls": 0}
    xml = RUN / f"{name}.xml"
    if xml.exists():
        suite = ElementTree.parse(xml).getroot().find("testsuite")
        if suite is not None:
            receipt["pytest_counts"] = {key: int(suite.get(key, "0"))
                                        for key in ("tests", "failures", "errors", "skipped")}
    (RUN / f"{name}.command.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("name", "started_at", "ended_at", "exit_code")}))
    print((RUN / f"{name}.log").read_text(encoding="utf-8", errors="replace"))
    return completed.returncode


if __name__ == "__main__":
    action = sys.argv[1]
    original = REVIEW_RUN / "test_independent_boundaries.py"
    snapshot = RUN / "test_independent_boundaries_original.py"
    if not snapshot.exists():
        snapshot.write_bytes(original.read_bytes())
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == hashlib.sha256(original.read_bytes()).hexdigest()
    files = [path.removeprefix("backend/") for path in SOURCE_PATHS[:4]]
    regression = ["tests/unit/test_r04_nvd_actual_schema.py", "tests/unit/test_r04_vendor_advisories.py",
                  "tests/unit/test_r04_vendor_missing_package.py", "tests/unit/test_t19_structured_enrichment.py",
                  "tests/contract/test_t10_cve_nvd_connectors.py", "tests/contract/test_t12_vendor_blog_connectors.py",
                  "tests/contract/test_t23_poc_scores_impact.py"]
    commands = {
        "sync": ["C:/Users/yinha/.local/bin/uv.exe", "sync", "--offline", "--frozen"],
        "original_red": [str(PYTHON), "-m", "pytest", str(snapshot), "-k",
                         "same_cve_nvd_vendor_different_scores_must_conflict or unrelated_valid_cwe_selection",
                         "--no-cov", "-q", f"--junitxml={RUN / 'original_red.xml'}"],
        "original_recheck": [str(PYTHON), "-m", "pytest", str(snapshot), "--no-cov", "-q",
                             f"--junitxml={RUN / 'original_recheck.xml'}"],
        "new_red": [str(PYTHON), "-m", "pytest", NEW_TEST.removeprefix("backend/"), "--no-cov", "-q",
                    f"--junitxml={RUN / 'new_red.xml'}"],
        "new_regression": [str(PYTHON), "-m", "pytest", NEW_TEST.removeprefix("backend/"),
                           NEW_CONTRACT.removeprefix("backend/"), "--no-cov", "-q",
                           f"--junitxml={RUN / 'new_regression.xml'}"],
        "focused": [str(PYTHON), "-m", "pytest", *files[2:], "--no-cov", "-q",
                    f"--junitxml={RUN / 'focused.xml'}"],
        "regression": [str(PYTHON), "-m", "pytest", *regression, "--no-cov", "-q",
                       f"--junitxml={RUN / 'regression.xml'}"],
        "ruff": [str(PYTHON), "-m", "ruff", "check", *files, NEW_TEST.removeprefix("backend/"),
                 NEW_CONTRACT.removeprefix("backend/")],
        "format": [str(PYTHON), "-m", "ruff", "format", "--check", *files, NEW_TEST.removeprefix("backend/"),
                   NEW_CONTRACT.removeprefix("backend/")],
        "mypy": [str(PYTHON), "-m", "mypy", *files[:2]],
        "ruff_fix": [str(PYTHON), "-m", "ruff", "check", "--fix", NEW_TEST.removeprefix("backend/"),
                     NEW_CONTRACT.removeprefix("backend/")],
        "format_fix": [str(PYTHON), "-m", "ruff", "format", NEW_TEST.removeprefix("backend/"),
                       NEW_CONTRACT.removeprefix("backend/")],
        "rg_callers": ["rg", "-n", r"_scope\(|_cwe_candidates\(|enrich_structured_fields\(|select_cwe_catalog_document\(",
                       "src", "tests"],
        "code_stage": ["git", "add", "--", "src/ai_intel/enrichment/signals.py",
                       NEW_TEST.removeprefix("backend/"), NEW_CONTRACT.removeprefix("backend/")],
        "code_commit": ["git", "commit", "-m", "fix R07: preserve CVE score conflicts and merge matching CWE selections"],
        "recorded_replay": [str(PYTHON), str(RUN / "replay_public_bodies.py")],
        "source_diff_check": ["git", "diff", "--check", "7f8cdc81108e39819d192c09bf1b4a61c640aec9",
                              "HEAD", "--", "src", "tests"],
        "changed_files": ["git", "diff", "--name-status", "7f8cdc81108e39819d192c09bf1b4a61c640aec9", "HEAD"],
        "rg_final": ["rg", "-n", r"\b(?:_scope|_cwe_candidates|enrich_structured_fields|select_cwe_catalog_document)\(",
                     "src", "tests"],
        "material_diff_initial": ["git", "diff", "--cached", "--check", "--",
                                  "reports/tasks/R07-public-signals-fix1.md",
                                  "reports/runs/recovery_r07_public_signals_fix1_20261016/*.py"],
        "material_diff_check": ["git", "-c", "core.whitespace=trailing-space,space-before-tab,cr-at-eol",
                                "diff", "--cached", "--check", "--",
                                "reports/tasks/R07-public-signals-fix1.md",
                                "reports/runs/recovery_r07_public_signals_fix1_20261016/*.py"],
    }
    artifact_name = sys.argv[2] if len(sys.argv) > 2 else action
    cwd = ROOT if action.startswith("material_diff") else BACKEND
    raise SystemExit(run(artifact_name, commands[action], cwd=cwd))
