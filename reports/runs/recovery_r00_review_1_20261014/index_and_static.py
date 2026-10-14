"""Build isolated narrow indexes and check the frozen review source."""

from run_commands import run, REVIEW
from pathlib import Path

CLI = ["wsl", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r00-review1-20261014",
       "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
LINUX = "/mnt/c/Users/yinha/.codex/worktrees/recovery-r00-review/dianzi"

run("cbm_index_scripts", CLI + ["index_repository", "--repo-path", LINUX + "/scripts", "--name", "dianzi-r00-review1-scripts-d752fe0", "--mode", "fast", "--persistence", "false"])
run("cbm_index_backend", CLI + ["index_repository", "--repo-path", LINUX + "/backend/src", "--name", "dianzi-r00-review1-backend-d752fe0", "--mode", "fast", "--persistence", "false"])
for name, tool, args in [
    ("cbm_schema", "get_graph_schema", ["--project", "dianzi-r00-review1-scripts-d752fe0"]),
    ("cbm_scripts_architecture", "get_architecture", ["--project", "dianzi-r00-review1-scripts-d752fe0", "--format", "json"]),
    ("cbm_load_json_callers", "trace_path", ["--project", "dianzi-r00-review1-scripts-d752fe0", "--function-name", "dianzi-r00-review1-scripts-d752fe0.verify_plan.load_json", "--direction", "inbound", "--depth", "3", "--format", "json"]),
    ("cbm_api_entry", "trace_path", ["--project", "dianzi-r00-review1-backend-d752fe0", "--function-name", "dianzi-r00-review1-backend-d752fe0.ai_intel.api.app.create_application", "--direction", "outbound", "--depth", "2", "--include-tests", "false", "--format", "json"]),
]:
    run(name, CLI + [tool] + args)
run("rg_plan_callers", ["rg", "-n", "load_json|check_recovery_manifest|check_task_state|run_all_checks|main\\(|create_application", "scripts", "tests/plan", "backend/src/ai_intel/api"])
paths = [str(REVIEW / "scripts/verify_plan.py"), str(REVIEW / "tests/plan")]
uv = [r"C:\Users\yinha\.local\bin\uv.exe", "run", "--locked", "--offline", "--no-sync"]
cwd = Path(r"D:\dianzi\backend")
run("ruff", uv + ["ruff", "check"] + paths, cwd)
run("format", uv + ["ruff", "format", "--check"] + paths, cwd)
run("mypy", uv + ["mypy", "--follow-imports=skip", str(REVIEW / "scripts/verify_plan.py")], cwd)
