"""Independent fixed-source and assets graph evidence, with explicit current cwd and commit."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PREFIX = ["wsl.exe", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]


def capture(label, tool, arguments):
    label += "_v2"
    argv = [*PREFIX, tool, json.dumps(arguments)]
    start = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    (RUN / (label + ".stdout.json")).write_text(result.stdout, encoding="utf-8")
    (RUN / (label + ".stderr.log")).write_text(result.stderr, encoding="utf-8")
    record = {"argv": argv, "cwd": str(ROOT), "started_at": start, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
              "exit_code": result.returncode, "head": "54f17c9a61d55af5ffe43e58d9252efad6317646", "source": "dcbc3d928b26f6755a5bfa71a3b70f71527bd832"}
    (RUN / (label + ".command.json")).write_text(json.dumps(record, indent=2) + "\n")
    assert result.returncode == 0
    assert not json.loads(result.stdout).get("isError", False)


def main():
    for suffix, path in [("src", "backend/src"), ("assets", "backend/src/ai_intel/assets")]:
        project = "r11-independent-fix1-54f17-dcbc-" + suffix + "-20261016"
        capture("cbm_" + suffix + "_index", "index_repository", {"repo_path": "/mnt/d/wt/r11-integrated-api-review1-fix1/" + path, "name": project, "mode": "fast"})
        for tool in ["get_graph_schema", "get_architecture"]:
            capture("cbm_" + suffix + "_" + tool, tool, {"project": project, "format": "json"})
        for function in (["create_application"] if suffix == "src" else ["build_inventory_router", "safe_sbom_sidecar", "_safe_source_field", "safe_sbom_snapshot", "get_snapshot_sbom"]):
            capture("cbm_" + suffix + "_trace_" + function, "trace_path", {"project": project, "function_name": function, "direction": "both", "depth": 3})
    print("12 independent CBM commands completed")


if __name__ == "__main__":
    main()
