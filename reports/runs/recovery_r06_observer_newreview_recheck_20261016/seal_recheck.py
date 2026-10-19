"""Seal this independent recheck and the final owned locked-runtime results."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PREP = RUN.parent / "recovery_r06_incremental_observation_preparation_20261016"
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-observer-newreview-recheck.md"
CODE = "1c4cce9770bfa29d08728a0131f7fc7fe714f9bc"
HEAD = "b08824f738ca185776916ae02689d8507f956c5c"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == HEAD
assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).strip()
frozen = []
for file in sorted(PREP.glob("*.py")):
    relative = file.relative_to(ROOT).as_posix()
    blob = subprocess.check_output(["git", "show", CODE + ":" + relative], cwd=ROOT)
    assert blob == file.read_bytes()
    frozen.append({"path": relative, "sha256": hashlib.sha256(blob).hexdigest()})
assert len(frozen) == 9
selected = ["owned_venv_sync", "owned_ruff", "owned_format", "owned_mypy", "owned_unit32", "owned_absent_gate", "owned_independent21", "owned_boundaries_sources_retry2", "cbm_help", "cbm_index_help", "cbm_schema_help", "cbm_index", "cbm_schema", "cbm_search_enqueue", "cbm_search_commit", "cbm_trace_enqueue", "cbm_trace_commit"]
receipts = []
for name in selected:
    receipt = json.loads((RUN / (name + "_receipt.json")).read_bytes())
    assert receipt["exit_code"] == receipt["expected_exit_code"]
    assert hashlib.sha256((RUN / receipt["log"]).read_bytes()).hexdigest() == receipt["log_sha256"]
    receipts.append(receipt)
unit = (RUN / "owned_unit32.log").read_text(encoding="utf-8")
assert re.search(r"Ran 32 tests in .*\n\nOK", unit)
mapping = json.loads((RUN / "owned_environment/independent21_mapping.json").read_bytes())
assert mapping["current_total"] == mapping["current_passed"] == 21 and mapping["current_failed"] == 0
boundaries = json.loads((RUN / "owned_environment/boundary_results.json").read_bytes())
assert boundaries["passed"] == boundaries["total"] == 8
locked = []
for name in ("pyproject.toml", "uv.lock"):
    original = (ROOT / "backend" / name).read_bytes()
    assert original == (RUN / "runtime_env" / name).read_bytes()
    locked.append({"path": "backend/" + name, "sha256": hashlib.sha256(original).hexdigest()})
python = str(RUN / "runtime_env/.venv/Scripts/python.exe")
inventory_code = "import importlib.metadata,json,sys; print(json.dumps({'python':sys.version,'packages':sorted((item.metadata['Name'],item.version) for item in importlib.metadata.distributions())},ensure_ascii=False))"
inventory = json.loads(subprocess.check_output([python, "-B", "-c", inventory_code], cwd=ROOT))
inventory.update({"mode": "owned_locked_offline_no_project_install", "inputs": locked, "no_network": True, "no_model_weights": True, "venv_bulk_files_archived": False})
(RUN / "runtime_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
entries = []
for path in sorted([REPORT, *RUN.rglob("*")]):
    if not path.is_file() or path.name in {"artifact_manifest.json", "artifact_manifest.sha256"} or path.is_relative_to(RUN / "runtime_env/.venv"):
        continue
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    entries.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest})
manifest = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "review_branch": "codex/r06-recheck", "review_worktree": str(ROOT), "reviewed_code_sha": CODE, "material_sha": "521b740612b2d0465f2be50cd58b5028f1c820b7", "supplement_sha": HEAD, "prior_review_manifest_sha256": "adef785ee9fbb5f3783945af095327ff455a4e8f3941a6a6de8e9a27c415ae37", "author_manifest_fix1_sha256": "b797ea19c6bb4f60373fbb8b9fced1111ab207a4eca34342f4b95a3bc0b27f46", "scope_verdict": "Ship: offline observer slice only", "accepted_registered": False, "full_R06_R20_R22_GC_ship": False, "report": REPORT.relative_to(ROOT).as_posix(), "frozen_code_files": frozen, "owned_runtime": "runtime_env/.venv", "owned_32_tests": {"passed": 32, "failed": 0, "skipped": 0}, "independent_original_21": {"passed": 21, "failed": 0, "skipped": 0, "original_red_15_of_21_retained": True}, "extra_synthetic_boundaries": {"passed": 8, "failed": 0}, "verification": {"unit": "passed", "contract": "passed", **{layer: "not_run" for layer in ("integration", "security", "frontend", "e2e", "live", "manual")}}, "cbm": "actual independent src-only CLI index and qualified traces; dynamic missing edges supplemented by AST/rg", "new_live_seconds": 0, "business_pg_connection": False, "environment_credentials_read": False, "product_service_start": False, "network": False, "source_test_progress_contract_changes": False, "push": False, "manifest_self_hash_excluded": True, "excluded_runtime_bulk": "runtime_env/.venv; reproducible frozen offline inputs and installed inventory retained", "final_receipts": receipts, "artifacts": entries}
content = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
(RUN / "artifact_manifest.json").write_bytes(content)
digest = hashlib.sha256(content).hexdigest()
(RUN / "artifact_manifest.sha256").write_text(digest + "  artifact_manifest.json\n", encoding="ascii")
print(json.dumps({"manifest": str(RUN / "artifact_manifest.json"), "manifest_sha256": digest, "report": str(REPORT), "artifacts": len(entries), "artifact_bytes": sum(item["bytes"] for item in entries), "verdict": "Ship: offline observer slice only"}))
