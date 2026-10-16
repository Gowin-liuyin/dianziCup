"""Record parser and loader caller provenance before the scalar boundary change."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
prefix = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--",
          "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli"]
project = "r07_inputs_fix3_src"
commands = [
    ("index", ["index_repository", "--repo-path", "/mnt/d/wt/r07-input-capabilities/backend/src",
               "--name", project, "--mode", "fast", "--persistence", "false"]),
    ("schema", ["get_graph_schema", "--project", project]),
    ("architecture", ["get_architecture", "--project", project, "--aspects", "all"]),
    ("parser", ["trace_path", "--project", project, "--function-name",
                project + ".ai_intel.enrichment.taxonomy_inputs.parse_atlas_catalogue", "--direction", "both", "--depth", "3"]),
    ("loader", ["trace_path", "--project", project, "--function-name",
                project + ".ai_intel.enrichment.taxonomy_inputs.load_taxonomy_catalogue", "--direction", "both", "--depth", "3"]),
    ("rg", None),
]
records = []
for label, args in commands:
    command = [*prefix, *args] if args else ["rg", "-n", "parse_atlas_catalogue|_check_yaml_node|load_taxonomy_catalogue", "backend/src", "backend/tests"]
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    (RUN / ("cbm_before_" + label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    records.append({"command": command, "cwd": str(ROOT), "started_at": started,
                    "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": result.returncode})
    assert result.returncode == 0
(RUN / "cbm_before_commands.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
print(json.dumps(records))
