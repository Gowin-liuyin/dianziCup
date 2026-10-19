"""为已冻结集成版本建立隔离源码索引并追踪来源生产调用链。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PROJECT = "dianzi-root-batch5-20261016-1833"
PREFIX = ["wsl", "-d", "Ubuntu-22.04", "--", "env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-batch5-20261016-1833", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
checks = [("index", ["index_repository", "--repo-path", "/mnt/d/dianzi/backend/src", "--mode", "full", "--name", PROJECT]), ("schema", ["get_graph_schema", "--project", PROJECT]), ("source_callers", ["trace_path", "--project", PROJECT, "--function-name", PROJECT + ".ai_intel.ingestion.source_documents.persist_source_response", "--direction", "both", "--depth", "2", "--max-output-tokens", "2500"])]
receipts = []
for label, arguments in checks:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(PREFIX + arguments, cwd=ROOT, capture_output=True, timeout=60, check=False)
    (RUN / ("batch5_cbm_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "source_sha": head, "source_tree": tree, "scope": "backend/src only, no secret/holdout/fixtures/reports", "cache_isolation_variable": "CBM_CACHE_DIR", "command": PREFIX + arguments, "cwd": str(ROOT), "exit_code": result.returncode}
    receipts.append(receipt)
    print(json.dumps({"label": label, "exit_code": result.returncode}))
    if result.returncode:
        break
(RUN / "batch5_cbm_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if all(item["exit_code"] == 0 for item in receipts) else 1)
