"""Cross-check the frozen repair's actual source, publication and authentication callers."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SHA = "dc04d193185324f6913cde8efc40f4b238047dd8"
PROJECT = "r07-pub-dc04-src"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
commands = [
    ("fixed_index", prefix + ["index_repository", "--repo-path", "/mnt/d/wt/r07-pub-combined/backend/src", "--name", PROJECT, "--mode", "fast"]),
    ("fixed_schema", prefix + ["get_graph_schema", "--project", PROJECT]),
    ("fixed_architecture", prefix + ["get_architecture", "--project", PROJECT]),
]
for name, function, direction in (
    ("input_dependencies", "ai_intel.enrichment.inputs.load_event_enrichment_inputs", "outbound"),
    ("publisher_dependencies", "ai_intel.enrichment.publication.publish_enrichment_attempts", "outbound"),
    ("publisher_callers", "ai_intel.enrichment.publication.publish_enrichment_attempts", "inbound"),
    ("source_writer_dependencies", "ai_intel.ingestion.source_documents.persist_source_response", "outbound"),
    ("public_signal_callers", "ai_intel.enrichment.signals.enrich_structured_fields", "inbound"),
):
    commands.append((name, prefix + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + function, "--direction", direction, "--depth", "2", "--max-output-tokens", "1800"]))
commands.append(("fixed_rg", ["rg", "-n", "publish_enrichment_attempts|load_event_enrichment_inputs|enrich_structured_fields|source:|knowledge-publication:|_scope", "backend/src", "backend/tests"]))
records = []
for label, argv in commands:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    with (RUN / (label + ".log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    records.append({"label": label, "argv": argv, "cwd": str(ROOT), "started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "exit_code": result.returncode, "code_sha": SHA, "project": PROJECT, "scope": "backend/src; code only; default assets excluded; no secrets/holdout/reports"})
    (RUN / "fixed_index_commands.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
print(json.dumps({"commands": len(records), "exit_code": 0, "code_sha": SHA}))
