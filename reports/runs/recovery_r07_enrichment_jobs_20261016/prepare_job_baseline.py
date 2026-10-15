"""Record the isolated locked environment and existing job/publication call graph."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SHA = "b3cc1a2ae231a4d1872f14d8a911d221c5272302"
PROJECT = "r07-enrichment-jobs-b3cc1a-src"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
commands = [
    ("locked_sync", ["C:/Users/yinha/.local/bin/uv.exe", "sync", "--project", "backend", "--frozen", "--offline", "--all-extras"]),
    ("baseline_index", prefix + ["index_repository", "--repo-path", "/mnt/d/wt/r07-enrichment-jobs/backend/src", "--name", PROJECT, "--mode", "fast"]),
    ("baseline_schema", prefix + ["get_graph_schema", "--project", PROJECT]),
    ("baseline_architecture", prefix + ["get_architecture", "--project", PROJECT]),
]
for name, function, direction in (
    ("enqueue_callers", "ai_intel.infrastructure.outbox.enqueue_job", "inbound"),
    ("executor_dependencies", "ai_intel.workers.executor.execute_job", "outbound"),
    ("publisher_dependencies", "ai_intel.enrichment.publication.publish_enrichment_attempts", "outbound"),
    ("generation_callers", "ai_intel.infrastructure.models.generation.GenerationClient.generate", "inbound"),
):
    commands.append((name, prefix + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + function, "--direction", direction, "--depth", "2", "--max-output-tokens", "2000"]))
commands.append(("baseline_rg", ["rg", "-n", "enqueue_job|JobExecutionContext|model_trace|job_payloads|enrichment_results|lock_authenticated_scope", "backend/src", "backend/tests"]))
records = []
for label, argv in commands:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    with (RUN / (label + ".log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    records.append({"label": label, "argv": argv, "cwd": str(ROOT), "started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "exit_code": result.returncode, "head": SHA, "project": PROJECT, "scope": "backend/src only; reports/secrets/holdout excluded; default assets excluded"})
    (RUN / "baseline_commands.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
print(json.dumps({"commands": len(records), "exit_code": 0, "head": SHA}))
