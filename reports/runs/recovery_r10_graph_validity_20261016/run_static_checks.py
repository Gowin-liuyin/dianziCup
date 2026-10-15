"""保存修复冻结版本的实际静态检查和官方 CBM 输出，不启动网络服务。"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FILES = [
    "src/ai_intel/knowledge/evidence_graph.py",
    "src/ai_intel/api/graph_routes.py",
    "tests/unit/test_r10_evidence_graph.py",
    "tests/contract/test_r10_graph_contract.py",
    "tests/security/test_r10_graph_boundary.py",
    "tests/integration/test_r10_evidence_graph_pg.py",
    "tests/integration/test_r10_graph_validity_pg.py",
]
CLI = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli"]


def main():
    assert not (RUN / "static_commands.json").exists()
    timestamp = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat()
    jobs = [
        ("ruff_frozen", [sys.executable, "-m", "ruff", "check", *FILES], ROOT / "backend"),
        ("format_frozen", [sys.executable, "-m", "ruff", "format", "--check", *FILES], ROOT / "backend"),
        ("mypy_frozen", [sys.executable, "-m", "mypy", *FILES[:2]], ROOT / "backend"),
        ("code_diff_check", ["git", "diff", "--check", "16803ce6be9ad6adb6d89f46c594cfa420190c24", "3516b9109b9b7f2c5691d78ad0439aea4a659f4f", "--", "backend", "docs/decisions/CR-R10_graph_validity.md"], ROOT),
        ("cbm_index", [*CLI, "index_repository", "--repo-path", "/mnt/d/wt/r10-pg-graph/backend/src", "--name", "r10_pg_graph_backend", "--mode", "fast", "--persistence", "false"], ROOT),
        ("cbm_architecture", [*CLI, "get_architecture", "--project", "r10_pg_graph_backend", "--aspects", '["all"]'], ROOT),
        ("cbm_graph_trace", [*CLI, "trace_path", "--project", "r10_pg_graph_backend", "--function-name", "r10_pg_graph_backend.ai_intel.knowledge.evidence_graph.EvidenceGraphReadService.event_graph", "--direction", "both", "--depth", "2"], ROOT),
        ("cbm_fence_trace", [*CLI, "trace_path", "--project", "r10_pg_graph_backend", "--function-name", "r10_pg_graph_backend.ai_intel.knowledge.evidence_graph.EvidenceGraphReadService.lock_graph_inputs", "--direction", "both", "--depth", "2"], ROOT),
    ]
    receipts = []
    for label, command, cwd in jobs:
        started = timestamp()
        result = subprocess.run(command, cwd=cwd, capture_output=True)
        (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
        receipts.append({"label": label, "command": command, "cwd": str(cwd), "started_at": started, "finished_at": timestamp(), "exit_code": result.returncode, "code_commit": "3516b9109b9b7f2c5691d78ad0439aea4a659f4f"})
        print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    (RUN / "static_commands.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
    return int(any(item["exit_code"] for item in receipts))


if __name__ == "__main__":
    raise SystemExit(main())
