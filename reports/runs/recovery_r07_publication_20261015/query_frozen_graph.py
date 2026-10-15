"""Refresh the exact source snapshot and retain qualified graph/caller evidence."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SHA = "23f518692abbf9c0d0b54b7081ddddfaa5f92dec"
PROJECT = "r07-publication-23f5186-src"
BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PREFIX = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", BINARY, "cli", "--json"]
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
assert not subprocess.check_output(["git", "status", "--porcelain", "--", "backend/src", "backend/tests"], cwd=ROOT, text=True).strip()
commands = [
    ("frozen_cbm_index", PREFIX + ["index_repository", "--repo-path", "/mnt/d/wt/r07-publication/backend/src", "--name", PROJECT, "--mode", "fast"]),
    ("frozen_cbm_schema", PREFIX + ["get_graph_schema", "--project", PROJECT]),
    ("frozen_cbm_architecture", PREFIX + ["get_architecture", "--project", PROJECT]),
]
for label, function, direction in (
    ("frozen_loader_dependencies", "ai_intel.enrichment.inputs.load_event_enrichment_inputs", "outbound"),
    ("frozen_publisher_dependencies", "ai_intel.enrichment.publication.publish_enrichment_attempts", "outbound"),
    ("frozen_knowledge_callers", "ai_intel.knowledge.persistence.KnowledgeRepository.publish", "inbound"),
    ("frozen_detail_dependencies", "ai_intel.api.knowledge_read_service.KnowledgeReadService.event_detail", "outbound"),
):
    commands.append((label, PREFIX + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + function, "--direction", direction, "--depth", "2", "--max-output-tokens", "2500"]))
commands.append(("frozen_rg_callers", ["rg", "-n", "ClaimSubmission|additional_sources|load_event_enrichment_inputs|publish_enrichment_attempts", "backend/src", "backend/tests"]))
receipts = []
for label, argv in commands:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=120)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"label": label, "argv": argv, "cwd": str(ROOT), "started_at": started,
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "exit_code": result.returncode, "code_sha": SHA, "project": PROJECT,
        "index_scope": "backend/src only; default assets excluded; no secrets/reports/holdout"})
    (RUN / "frozen_cbm_commands.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
print(json.dumps({"commands": len(receipts), "exit_code": 0, "code_sha": SHA}))
