"""Record offline evidence commands without reading runtime secrets or holdout data."""

import hashlib
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PROJECT = "nativecpu_diagnostic_1927_src"
COMMANDS = [
    ("git_head", ["git", "rev-parse", "HEAD"]),
    ("git_branch", ["git", "branch", "--show-current"]),
    ("git_status", ["git", "status", "--short"]),
    ("cbm_help", ["wsl", "--exec", CBM, "--help"]),
    ("cbm_index_help", ["wsl", "--exec", CBM, "cli", "index_repository", "--help"]),
    ("cbm_trace_help", ["wsl", "--exec", CBM, "cli", "trace_path", "--help"]),
    ("cbm_index", ["wsl", "--exec", CBM, "cli", "--json", "index_repository", "--repo-path", "/tmp/dianzi-nativecpu-diagnostic-20261015/src", "--mode", "fast", "--name", PROJECT, "--persistence", "false"]),
    ("cbm_limiter", ["wsl", "--exec", CBM, "cli", "--json", "trace_path", "--function-name", "bound_process_resources", "--project", PROJECT, "--direction", "both", "--depth", "5", "--include-evidence", "true", "--format", "json", "--max-output-tokens", "5000"]),
    ("cbm_semantic", ["wsl", "--exec", CBM, "cli", "--json", "trace_path", "--function-name", "_bound_worker_memory", "--project", PROJECT, "--direction", "inbound", "--depth", "5", "--include-evidence", "true", "--format", "json"]),
    ("cbm_pdf", ["wsl", "--exec", CBM, "cli", "--json", "trace_path", "--function-name", "_bound_memory", "--project", PROJECT, "--direction", "inbound", "--depth", "5", "--include-evidence", "true", "--format", "json"]),
    ("rg_callers", ["rg", "-n", "bound_process_resources|process_limits|_bound_memory|_bound_worker_memory|_run_worker|_pdf_worker", "backend/src", "backend/tests/unit/test_r05_process_limits.py"]),
    ("rg_failures", ["rg", "-n", "-g", "*.log", "TimeoutExpired|test_real_native_cpu_limit_terminates_busy_child", "D:/wt/r06-feeds/reports/runs/recovery_r06_feed_parsers_20261015", "D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015"]),
]
commands = []
for name, command in COMMANDS:
    started = time.perf_counter()
    record = {"name": name, "command": command, "cwd": str(ROOT), "started_at": datetime.now(timezone.utc).isoformat()}
    process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=40, check=False)
    (OUTPUT / f"{name}.log").write_bytes(process.stdout + process.stderr)
    record.update(exit_code=process.returncode, wall_seconds=time.perf_counter() - started, completed_at=datetime.now(timezone.utc).isoformat(), log=f"{name}.log")
    commands.append(record)
(OUTPUT / "audit_commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")

original_root = Path("D:/wt/r06-feeds/reports/runs/recovery_r06_feed_parsers_20261015")
evidence = []
for name in ("unit_final", "unit_recheck", "fix1_green_combined", "fix1_combined_recheck"):
    metadata = json.loads((original_root / f"{name}.json").read_text(encoding="utf-8-sig"))
    log = original_root / f"{name}.log"
    xml = original_root / f"{name}.xml"
    tree = ET.parse(xml)
    matching = [case for case in tree.iter("testcase") if case.get("name") == "test_real_native_cpu_limit_terminates_busy_child"]
    evidence.append({"metadata": metadata, "log": str(log), "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(), "junit": str(xml), "junit_sha256": hashlib.sha256(xml.read_bytes()).hexdigest(), "native_cpu_test": [{"attributes": case.attrib, "failures": [(failure.get("message"), failure.text) for failure in case.findall("failure")]} for case in matching]})
(OUTPUT / "original_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

paths = [ROOT / "AGENTS.md", ROOT / "docs/plan/00_execution_map.md", ROOT / "docs/plan/06_testing_and_evaluation.md", ROOT / "docs/plan/09_operations_delivery.md", ROOT / "docs/plan/12_recovery_task_cards_20261014.md", ROOT / "progress/task_state.json", ROOT / "progress/context_handoff.md", ROOT / "backend/src/ai_intel/infrastructure/process_limits.py", ROOT / "backend/tests/unit/test_r05_process_limits.py", Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md")]
(OUTPUT / "input_hashes.json").write_text(json.dumps([{ "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths], indent=2), encoding="utf-8")
print(json.dumps({"commands": len(commands), "nonzero_commands": [item["name"] for item in commands if item["exit_code"]], "original_runs": len(evidence)}))
