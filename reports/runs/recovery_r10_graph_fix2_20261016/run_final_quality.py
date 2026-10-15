"""冻结代码静态检查及作者独有 CBM 索引，保留实际命令和 stdout。"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CODE = "08b141bd437c1de70a8435a1f7f6c448a131ed0d"
FILES = ["src/ai_intel/knowledge/evidence_graph.py", "src/ai_intel/api/graph_routes.py", "src/ai_intel/enrichment/field_sources.py", "tests/unit/test_r10_evidence_graph.py", "tests/unit/test_r10_relation_polarity.py", "tests/contract/test_r10_graph_contract.py", "tests/security/test_r10_graph_boundary.py", "tests/integration/test_r10_evidence_graph_pg.py", "tests/integration/test_r10_graph_validity_pg.py", "tests/integration/test_r10_graph_fix2_pg.py", "tests/integration/test_r10_graph_source_coverage_pg.py"]
CLI = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli"]
jobs = [
    ("ruff_frozen", [sys.executable, "-m", "ruff", "check", *FILES], ROOT / "backend"),
    ("format_frozen", [sys.executable, "-m", "ruff", "format", "--check", *FILES], ROOT / "backend"),
    ("mypy_frozen", [sys.executable, "-m", "mypy", *FILES[:3]], ROOT / "backend"),
    ("code_diff_frozen", ["git", "diff", "--check", "29e1ebddca5cbadffc8c6533bdeeb08b8d63e469", CODE, "--", "backend", "docs/decisions/CR-R10_graph_fix2.md"], ROOT),
    ("cbm_index_after", [*CLI, "index_repository", "--repo-path", "/mnt/d/wt/r10-graph-fix2/backend/src", "--name", "r10_graph_fix2_backend", "--mode", "fast", "--persistence", "false"], ROOT),
    ("cbm_architecture_after", [*CLI, "get_architecture", "--project", "r10_graph_fix2_backend", "--aspects", "all"], ROOT),
    ("cbm_field_after", [*CLI, "trace_path", "--project", "r10_graph_fix2_backend", "--function-name", "r10_graph_fix2_backend.ai_intel.enrichment.field_sources.validate_field_candidate", "--direction", "both", "--depth", "3"], ROOT),
    ("cbm_fence_after", [*CLI, "trace_path", "--project", "r10_graph_fix2_backend", "--function-name", "r10_graph_fix2_backend.ai_intel.knowledge.evidence_graph.EvidenceGraphReadService.lock_graph_inputs", "--direction", "both", "--depth", "2"], ROOT),
]
assert not (RUN / "final_quality_commands.json").exists()
receipts = []
for label, command, cwd in jobs[:4]:
    label = label.replace("frozen", "final")
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    result = subprocess.run(command, cwd=cwd, capture_output=True)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"command": command, "cwd": str(cwd), "started_at": started, "finished_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "exit_code": result.returncode, "code_commit": CODE})
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
(RUN / "final_quality_commands.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
