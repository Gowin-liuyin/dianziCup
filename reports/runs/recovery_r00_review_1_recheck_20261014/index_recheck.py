"""Refresh the new SHA's independent narrow source indexes."""

from recheck_commands import run, REVIEW, LINUX

CLI = ["wsl", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r00-review1-recheck-20261014",
       "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
for scope, directory in (("scripts", "scripts"), ("backend", "backend/src")):
    run("cbm_index_" + scope, CLI + ["index_repository", "--repo-path", LINUX + "/" + directory,
        "--name", "dianzi-r00-recheck1-" + scope + "-15d0272", "--mode", "fast", "--persistence", "false"])
run("cbm_state_callers", CLI + ["trace_path", "--project", "dianzi-r00-recheck1-scripts-15d0272",
    "--function-name", "dianzi-r00-recheck1-scripts-15d0272.verify_plan.check_task_state", "--direction", "inbound", "--depth", "3", "--format", "json"])
run("cbm_load_json_callers", CLI + ["trace_path", "--project", "dianzi-r00-recheck1-scripts-15d0272",
    "--function-name", "dianzi-r00-recheck1-scripts-15d0272.verify_plan.load_json", "--direction", "inbound", "--depth", "3", "--format", "json"])
run("rg_slice_callers", ["rg", "-n", "check_task_state|STATE_RECOVERY_REQUIRED_SLICE|STATE_RECOVERY_OUTPUT_SLICE|slice_acceptance|load_json", "scripts", "tests/plan"])
run("wsl_source_hashes", ["wsl", "--exec", "sha256sum", LINUX + "/contracts/requirements.json",
    LINUX + "/contracts/task_manifest.json", LINUX + "/fixtures/synthetic/pilot_cases.json"])
