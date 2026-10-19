"""Copy an approved read-only kernel probe, writing only into this reviewer run."""

import os
from pathlib import Path

from review_runner import ROOT, RUN, receipt

original = Path("D:/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/inspect_security.py")
body = original.read_text(encoding="utf-8")
body = body.replace("import runtime", """import importlib.util
import sys

runtime_path = '/mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/runtime.py'
spec = importlib.util.spec_from_file_location('runtime', runtime_path)
runtime = importlib.util.module_from_spec(spec)
sys.modules['runtime'] = runtime
spec.loader.exec_module(runtime)
runtime.OUTPUT = Path(__file__).resolve().parent""")
body = body.replace('container = runtime.inspect_container(resource["container_id"])', '''assert resource["container_id"] == "2cbf8058a220f4b3bc0d4da779f06ddaa314f7a87feeac32ab64b18d0735bf99"
assert resource["deadline"] == "2026-10-16T19:35:43.312788+08:00"
assert runtime.now() < runtime.datetime.fromisoformat(resource["deadline"])
container = runtime.inspect_container(resource["container_id"])''')
(RUN / "resource_caps.py").write_text(body, encoding="utf-8", newline="\n")
command = ["wsl", "--user", "root", "--exec", "/usr/bin/python3", "-B", "/mnt/d/wt/r10-neo4j-projection-review1-fix2/reports/runs/recovery_r10_neo4j_projection_review1_fix2_20261016/resource_caps.py"]
raise SystemExit(receipt("resource_caps_root", command, ROOT, dict(os.environ)))
