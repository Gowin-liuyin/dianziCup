"""Use a private source-only CBM graph for this frozen review."""
import json
import subprocess
from pathlib import Path
from review_runner import ROOT, RUN, now

BASE = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env",
        "CBM_CACHE_DIR=/tmp/dianzi-cbm-r06-document-api-review-20261015",
        "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
PROJECT = "dianzi-r06-document-api-review-72eb1c"

COMMANDS = {
    "index": ["index_repository", "--repo-path", "/mnt/d/wt/r06-document-api-review/backend/src", "--name", PROJECT, "--mode", "fast"],
    "app": ["trace_path", "--project", PROJECT, "--function-name", "create_application", "--direction", "outbound", "--include-tests", "false"],
    "router": ["trace_path", "--project", PROJECT, "--function-name", "build_document_router", "--direction", "both", "--include-tests", "false"],
    "evidence": ["trace_path", "--project", PROJECT, "--function-name", "_evidence_rows", "--direction", "both", "--include-tests", "false"],
    "auth": ["trace_path", "--project", PROJECT, "--function-name", "lock_authenticated_scope", "--direction", "both", "--include-tests", "false"],
    "public": ["trace_path", "--project", PROJECT, "--function-name", "read_public_revision_evidence", "--direction", "both", "--include-tests", "false"],
}
for label, args in COMMANDS.items():
    started = now()
    result = subprocess.run(BASE + args, cwd=ROOT, capture_output=True, timeout=60, check=False)
    (RUN / ("cbm_" + label + ".stdout.json")).write_bytes(result.stdout)
    (RUN / ("cbm_" + label + ".stderr.log")).write_bytes(result.stderr)
    (RUN / ("cbm_" + label + ".command.json")).write_text(json.dumps({"argv": BASE + args, "cwd": str(ROOT), "started_at": started, "ended_at": now(), "exit_code": result.returncode, "scope": "backend/src only; no reports, fixtures, secrets or holdout", "head": "72eb1c0235805facd7f41310e5af5a110d0e0bad"}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode}))
