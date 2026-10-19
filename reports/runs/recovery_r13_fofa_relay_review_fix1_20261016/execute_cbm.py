"""追踪固定版本的专用模块及其公共网络依赖。"""

import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = sys.executable
CLI = ["wsl.exe", "--exec", "env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r13-relay-review-fix1-20261016", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli"]
SRC = "dianzi_r13_relay_review_fix1_src_20261016"
ASSETS = "dianzi_r13_relay_review_fix1_assets_20261016"
COMMANDS = [
    ("cbm_schema", [*CLI, "get_graph_schema", "--project", SRC, "--format", "json"]),
    ("cbm_assets_schema", [*CLI, "get_graph_schema", "--project", ASSETS, "--format", "json"]),
]
for label, project, function in [
    ("cbm_gateway_trace", SRC, f"{SRC}.ai_intel.infrastructure.network.create_network_gateway"),
    ("cbm_credentials_trace", SRC, f"{SRC}.ai_intel.infrastructure.network.OriginCredentials.inject"),
    ("cbm_fetch_trace", SRC, f"{SRC}.ai_intel.infrastructure.network.NetworkGateway.fetch"),
    ("cbm_relay_init_trace", ASSETS, f"{ASSETS}.fofa_relay.FofaRelayClient.__init__"),
    ("cbm_relay_probe_trace", ASSETS, f"{ASSETS}.fofa_relay.FofaRelayClient.probe_account"),
]:
    COMMANDS.append((label, [*CLI, "trace_path", "--function-name", function, "--project", project, "--direction", "both", "--depth", "3", "--format", "json"]))
failed = []
for label, command in COMMANDS:
    result = subprocess.run([PYTHON, str(RUN / "run_command.py"), label, ".", *command], cwd=ROOT, check=False)
    if result.returncode:
        failed.append(label)
print("Failed graph checks:", failed)
raise SystemExit(bool(failed))
