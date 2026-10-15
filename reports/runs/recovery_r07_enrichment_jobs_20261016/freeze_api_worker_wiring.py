"""Freeze the verified default entry before integrating separately reviewed source changes."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
FILES = [
    "backend/src/ai_intel/api/app.py", "backend/src/ai_intel/api/source_routes.py",
    "backend/src/ai_intel/api/enrichment_contracts.py", "backend/src/ai_intel/api/enrichment_routes.py",
    "backend/src/ai_intel/api/job_routes.py", "backend/src/ai_intel/enrichment/runtime_policy.py",
    "backend/src/ai_intel/infrastructure/settings.py", "backend/src/ai_intel/workers/runtime.py",
    "backend/tests/contract/test_r07_enrichment_api_response.py",
    "backend/tests/contract/test_r07_enrichment_runtime_policy.py",
    "backend/tests/integration/test_r07_enrichment_api_pg.py",
    "docs/decisions/CR-R07_enrichment_jobs.md",
]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip()
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
subprocess.run(["git", "add", "--", *FILES], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
assert set(subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()) == set(FILES)
diff = subprocess.check_output(["git", "diff", "--cached"], cwd=ROOT)
(RUN / "api_worker_staged.diff").write_bytes(diff)
with (RUN / "api_worker_code_commit.log").open("xb") as output:
    result = subprocess.run(["git", "commit", "-m", "R07 wire durable enrichment through authenticated default API and worker"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=60)
assert result.returncode == 0
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "files": FILES, "staged_diff_sha256": hashlib.sha256(diff).hexdigest(), "checks": {"related_pure": 194, "api_pg": 9, "execution_pg_batch": "29 pass/1 artifact-directory instrumentation failure; exact original failed case passed after creating declared output directory", "metadata_pg": 20, "mypy_source_files": 117, "ruff_and_format_files": 11}, "status": "awaiting_review", "paid_source_wire": 0, "celery_broker_process_e2e": "not_run", "push": "not_run"}
(RUN / "api_worker_code_freeze_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
