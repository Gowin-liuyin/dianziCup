"""Record independent owned-source index and the two actual shared-validator callers."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
prefix = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--",
          "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli"]
commands = [
    ("index", ["index_repository", "--repo-path", "/mnt/d/wt/r07-input-capabilities/backend/src",
               "--name", "r07_inputs_backend", "--mode", "fast", "--persistence", "false"]),
    ("model", ["trace_path", "--project", "r07_inputs_backend", "--function-name",
               "r07_inputs_backend.ai_intel.enrichment.model_fields._generate_field", "--direction", "both", "--depth", "3"]),
    ("graph", ["trace_path", "--project", "r07_inputs_backend", "--function-name",
               "r07_inputs_backend.ai_intel.knowledge.evidence_graph.EvidenceGraphReadService._validated_support", "--direction", "both", "--depth", "3"]),
]
records = []
for label, args in commands:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    result = subprocess.run([*prefix, *args], cwd=ROOT, capture_output=True, text=True)
    (RUN / ("cbm_context_seam_before_" + label + ".log")).write_text(result.stdout + result.stderr)
    records.append({"command": [*prefix, *args], "cwd": str(ROOT), "started_at": started,
                    "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": result.returncode})
    assert result.returncode == 0
(RUN / "cbm_context_seam_before_commands.json").write_text(json.dumps(records, indent=2))
print(json.dumps(records))
