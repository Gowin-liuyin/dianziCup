"""Small offline assertions for run bounds and actual Job readback."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from ai_intel.ingestion.source_jobs import SOURCE_PAGE_DELAY_SECONDS, SourcePageRequest, source_page_url
from collect import MAXIMUM_ROUNDS, MAXIMUM_SECONDS, ROUND_SECONDS
from runtime_limits import CPU_SECONDS_TOTAL, OwnedJob
from supervise import CODE_SHA, MAXIMUM_SOURCE_ATTEMPTS, MAXIMUM_SOURCE_JOBS, ROOT, watchdog_reason

RUN = Path(__file__).resolve().parent
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == CODE_SHA
assert MAXIMUM_ROUNDS == 12 and ROUND_SECONDS == 1800 and MAXIMUM_SECONDS == 21600
assert MAXIMUM_ROUNDS * 2 * 20 == MAXIMUM_SOURCE_JOBS == 480
assert MAXIMUM_SOURCE_ATTEMPTS == MAXIMUM_SOURCE_JOBS * 3 == 1440
assert SOURCE_PAGE_DELAY_SECONDS >= 7
assert source_page_url("nvd_ollama", {}) == "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=20&startIndex=0"
assert source_page_url("vllm_vendor", {}) == "https://api.github.com/repos/vllm-project/vllm/security-advisories?per_page=10&state=published"
for invalid in ({"source_kind": "arbitrary_url"}, {"source_kind": "nvd_ollama", "remaining_pages": 21}):
    try:
        SourcePageRequest.model_validate({"window_end": datetime.now(ZoneInfo("Asia/Shanghai")), **invalid})
    except ValidationError:
        pass
    else:
        raise AssertionError("source boundary accepted invalid request")
assert watchdog_reason(35, 0, 0, 0) is None
assert watchdog_reason(35.01, 0, 0, 0) == "source_job_watchdog"
assert watchdog_reason(None, 480, 0, 0) == "source_call_budget"
assert watchdog_reason(None, 0, 1440, 0) == "source_call_budget"
assert watchdog_reason(None, 0, 0, CPU_SECONDS_TOTAL) == "aggregate_cpu_budget"
job = OwnedJob()
usage = job.usage()
assert usage["active_processes"] >= 1
assert usage["cpu_seconds"] >= 0
receipt = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": CODE_SHA, "exit_code": 0, "selfcheck_runs": 1, "invalid_source_cases": 2, "actual_windows_job_limits_read_back": True, "job_usage": usage, "source_network_calls": 0, "scope": "Run control boundary assertions; no claim of product unit/contract or integration pass."}
(RUN / "selfcheck.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
