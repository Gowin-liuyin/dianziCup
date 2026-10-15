"""Freeze the tested private seam before delegating non-overlapping job execution code."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
files = [
    "backend/src/ai_intel/enrichment/job_contracts.py",
    "backend/src/ai_intel/enrichment/job_models.py",
    "backend/migrations/versions/0017_enrichment_job_workflows.py",
    "backend/tests/contract/test_r07_enrichment_job_request.py",
    "backend/tests/contract/test_r07_enrichment_execution_policy.py",
    "backend/tests/integration/test_r07_enrichment_job_metadata_pg.py",
    "docs/decisions/CR-R07_enrichment_jobs.md",
]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
subprocess.run(["git", "add", "--", *files], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()
assert set(staged) == set(files)
(RUN / "workflow_contract_staged.diff").write_bytes(subprocess.check_output(["git", "diff", "--cached"], cwd=ROOT))
subprocess.run(["git", "commit", "-m", "R07 define durable workflow request policy and job reservation metadata"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
receipt = {
    "started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "files": files,
    "scope": "tested private seam awaiting independent review; no worker/API registration",
    "checks": {"request_policy_contract": 40, "forward_metadata_pg": 20},
    "pushes": 0,
}
(RUN / "freeze_workflow_contract_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
