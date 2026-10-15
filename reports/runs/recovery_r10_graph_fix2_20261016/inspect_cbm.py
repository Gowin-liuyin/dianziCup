"""本作者独有源码索引及修改前 shared validator 调用图，实际 CLI stdout 原样保存。"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CLI = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"]
jobs = [
    ("help", ["--help"]),
    ("schema", ["cli", "get_graph_schema"]),
    ("index_before", ["cli", "index_repository", "--repo-path", "/mnt/d/wt/r10-graph-fix2/backend/src", "--name", "r10_graph_fix2_backend", "--mode", "fast", "--persistence", "false"]),
    ("architecture_before", ["cli", "get_architecture", "--project", "r10_graph_fix2_backend", "--aspects", "all"]),
    ("field_callers_before", ["cli", "trace_path", "--project", "r10_graph_fix2_backend", "--function-name", "r10_graph_fix2_backend.ai_intel.enrichment.field_sources.validate_field_candidate", "--direction", "both", "--depth", "3"]),
    ("model_before", ["cli", "trace_path", "--project", "r10_graph_fix2_backend", "--function-name", "r10_graph_fix2_backend.ai_intel.enrichment.model_fields.generate_model_field_attempts", "--direction", "both", "--depth", "2"]),
    ("fence_before", ["cli", "trace_path", "--project", "r10_graph_fix2_backend", "--function-name", "r10_graph_fix2_backend.ai_intel.knowledge.evidence_graph.EvidenceGraphReadService.lock_graph_inputs", "--direction", "both", "--depth", "2"]),
]
receipts = []
for label, arguments in jobs:
    assert not (RUN / ("cbm_" + label + ".log")).exists()
    command = [*CLI, *arguments]
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    (RUN / ("cbm_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"command": command, "cwd": str(ROOT), "started_at": started, "finished_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "exit_code": result.returncode})
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
(RUN / "cbm_before_commands.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
