"""Record bounded, source-only inspection commands for the R07 preflight."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("D:/dianzi")
RUN = ROOT / "reports/runs/recovery_r07_preflight_20261015"
PROJECT = "dianzi-r07-preflight-0a45185"
CBM = [
    "wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-r07-preflight-20261015",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json",
]


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def execute(label: str, argv: list[str], timeout: int = 60) -> None:
    started_at = now()
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=timeout, check=False)
    (RUN / f"{label}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{label}.stderr.log").write_bytes(result.stderr)
    (RUN / f"{label}.command.json").write_text(
        json.dumps({"argv": argv, "cwd": str(ROOT), "started_at": started_at,
                    "ended_at": now(), "exit_code": result.returncode,
                    "scope": "read-only; CBM backend/src only; no secrets, reports, fixtures or holdout indexed"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)


if __name__ == "__main__":
    execute("baseline", ["git", "rev-parse", "HEAD", "HEAD:backend/src"])
    execute("cbm_index", CBM + ["index_repository", "--repo-path", "/mnt/d/dianzi/backend/src",
                                "--name", PROJECT, "--mode", "fast"], 90)
    execute("cbm_architecture", CBM + ["get_architecture", "--project", PROJECT])
    execute("cbm_schema", CBM + ["get_graph_schema", "--project", PROJECT])
    for function_name in ("create_application", "configure_worker", "publish_enrichment_batch",
                          "parse_extraction_payload", "enrich_event", "build_knowledge_router"):
        execute(f"cbm_trace_{function_name}", CBM + ["trace_path", "--project", PROJECT,
                "--function-name", function_name, "--direction", "both", "--include-tests", "false"])
