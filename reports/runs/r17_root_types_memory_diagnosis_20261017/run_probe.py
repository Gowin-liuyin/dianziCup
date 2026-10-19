"""Delegate one read-only input probe to the existing bounded UI supervisor."""

import importlib.util
import json
import os
import sys
from pathlib import Path


RUN = Path(__file__).parent
REVIEW = Path("D:/wt/r17-fix3-review/reports/runs/r17_fix3_review_20261017")
sys.path.insert(0, str(REVIEW))
spec = importlib.util.spec_from_file_location("input_probe_checks", REVIEW / "bounded_checks.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
checks.ROOT = Path("D:/dianzi")
checks.RUN = RUN
checks.BASELINE = "3fd9cd68f292afcd1b88ca55f218c4e869e8f706"
checks.QUALIFIED = "6ed92b802a8126855dac3ce16d7c35e93305ff2b"
limiter_path = Path("D:/wt/r06-activation-database-fix5-20261017/reports/runs/recovery_r06_activation_prep_20261016/candidate/core/runtime_limits.py")
job_spec = importlib.util.spec_from_file_location("input_probe_job", limiter_path)
limiter = importlib.util.module_from_spec(job_spec)
job_spec.loader.exec_module(limiter)
limiter.MEMORY_TOTAL = 1024**3
limiter.CPU_RATE = max(1, 20000 // os.cpu_count())
owned_job = limiter.OwnedJob()
before_limits = owned_job.query(9, limiter.ExtendedLimits)
before_rate = owned_job.query(15, limiter.CpuRate)
command = ["C:/Program Files/nodejs/node.exe", "--max-old-space-size=384", "--max-semi-space-size=8", "--expose-gc", str(RUN / "input_probe.cjs")]
exit_code = checks.execute("input_probe", command, timeout=15, process_cap=10)
result = {"processMemoryLimit": before_limits.process_memory, "jobMemoryLimit": before_limits.job_memory, "limitFlags": before_limits.basic.flags, "cpuRateFlags": before_rate.flags, "cpuRate": before_rate.rate, "logicalCpuCount": os.cpu_count(), "usage": owned_job.usage(), "exitCode": exit_code}
with (RUN / "input_probe.native_limits.json").open("x", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2)
    handle.write("\n")
print(json.dumps(result))
raise SystemExit(exit_code)
