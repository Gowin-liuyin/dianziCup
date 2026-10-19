"""Index frozen source only and record CLI output with exact argv."""
import sys
from offline_runner import ROOT, execute

PREFIX = "dianzi-r17-real-browser-review1-20261016"
BASE = ["wsl", "-d", "Ubuntu-22.04", "--", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
label = sys.argv[1]
commands = {
    "frontend_index": ["index_repository", "--repo-path", "/mnt/d/wt/r17-real-sbom-browser-review1/frontend/src", "--name", PREFIX + "-frontend", "--mode", "full", "--persistence", "false"],
    "backend_index": ["index_repository", "--repo-path", "/mnt/d/wt/r17-real-sbom-browser-review1/backend/src", "--name", PREFIX + "-backend", "--mode", "fast", "--persistence", "false"],
    "assets_index": ["index_repository", "--repo-path", "/mnt/d/wt/r17-real-sbom-browser-review1/backend/src/ai_intel/assets", "--name", PREFIX + "-assets", "--mode", "full", "--persistence", "false"],
}
if label not in commands:
    project = PREFIX + "-" + sys.argv[2]
    if label.startswith("schema"):
        commands[label] = ["get_graph_schema", "--project", project, "--format", "json", "--diagnostics", "full", "--limit", "5"]
    elif label.startswith("architecture"):
        commands[label] = ["get_architecture", "--project", project, "--format", "json"]
    else:
        commands[label] = ["trace_path", "--project", project, "--function-name", sys.argv[3], "--direction", "both", "--depth", "4", "--format", "json", "--max-output-tokens", "6000"]
raise SystemExit(execute(label, BASE + commands[label], ROOT))
