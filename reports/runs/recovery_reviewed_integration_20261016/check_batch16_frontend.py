"""Check the integrated UI with the independent review's bounded native runner."""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
REVIEW = Path("D:/wt/r17-fix3-review/reports/runs/r17_fix3_review_20261017")
sys.path.insert(0, str(REVIEW))
spec = importlib.util.spec_from_file_location("ui_review_checks", REVIEW / "bounded_checks.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
checks.ROOT, checks.RUN = ROOT, RUN
checks.BASELINE = "0f8c1f6d047387cfca8a62f8dbc352b8c6415b96"
checks.QUALIFIED = "4fa72a27562ddd37d1344cec80939fa186b2e254"
limiter_path = Path("D:/wt/r06-activation-database-fix5-20261017/reports/runs/"
                    "recovery_r06_activation_prep_20261016/candidate/core/runtime_limits.py")
job_spec = importlib.util.spec_from_file_location("ui_owned_job", limiter_path)
limiter = importlib.util.module_from_spec(job_spec)
job_spec.loader.exec_module(limiter)
limiter.MEMORY_TOTAL = 1024**3
limiter.CPU_RATE = max(1, 20000 // os.cpu_count())
owned_job = limiter.OwnedJob()
node = "C:/Program Files/nodejs/node.exe"
mode = sys.argv[1]
commands = {
    "types": [node, "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"],
    "types_gc": [node, "--max-old-space-size=256", "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"],
    "types_bounded_gc": [node, "--max-old-space-size=384", "--max-semi-space-size=8",
                         "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"],
    "lint": [node, "node_modules/eslint/bin/eslint.js", "."],
    "lint_bounded_gc": [node, "--max-old-space-size=384", "--max-semi-space-size=8",
                        "node_modules/eslint/bin/eslint.js", "."],
    "tests": [node, "node_modules/vitest/vitest.mjs", "run", "--pool=threads",
              "--maxWorkers=1", "--no-file-parallelism", "src/features/questions",
              "src/api/client.test.ts", "src/App.test.tsx",
              "--reporter=junit", "--outputFile=" + str(RUN / "batch16_ui_tests.xml")],
    "build": [node, "node_modules/vite/bin/vite.js", "build", "--outDir",
              "D:/dianzi-runtime-cache/root-batch16-ui-20261017/dist"],
    "build_bounded_gc": [node, "--max-old-space-size=384", "--max-semi-space-size=8",
                         "node_modules/vite/bin/vite.js", "build", "--outDir",
                         "D:/dianzi-runtime-cache/root-batch16-ui-20261017/dist"],
}
raise SystemExit(checks.execute("batch16_ui_" + mode, commands[mode], timeout=60, process_cap=10))
