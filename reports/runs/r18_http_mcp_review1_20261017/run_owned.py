"""Independent R18 reviewer bounded runner using Root instrumentation."""

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
HELPER = Path("D:/dianzi/reports/runs/recovery_reviewed_integration_20261016/batch13_checks_helper.py")
LIMITS = Path("D:/wt/r06-activation-database-fix5-20261017/reports/runs/recovery_r06_activation_prep_20261016/candidate/core/runtime_limits.py")
PYTHON = "C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe"
SITE_PACKAGES = "D:/dianzi/backend/.venv/Lib/site-packages"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(HELPER.parent))
helper = load_module("r18_root_checks_helper", HELPER)
limits = load_module("r18_fixed_runtime_limits", LIMITS)
helper.ROOT = ROOT
helper.RUN = RUN
helper.PYTHON = PYTHON
helper.BASELINE = "3fd9cd68"
helper.QUALIFIED = "ccbbf3f5688bc57a81c881504a09ea5d18471387; source9fb558aa"
original_environment = helper.environment


def environment():
    configured = original_environment()
    for name in tuple(configured):
        if name.startswith(("DIANZI_API_", "DIANZI_MCP_")):
            configured.pop(name)
    configured["PYTHONPATH"] = os.pathsep.join(
        [SITE_PACKAGES, str(ROOT / "sdk/python"), str(ROOT / "sdk/python/tests"), str(ROOT)]
    )
    configured["SDK_TEST_EVIDENCE_DIR"] = str(RUN / "test_observations")
    return configured


helper.environment = environment
limits.MEMORY_TOTAL = 1024**3
limits.CPU_RATE = max(1, 20000 // (os.cpu_count() or 1))
job = limits.OwnedJob()
label, module, *arguments = sys.argv[1:]
if label.startswith("native"):
    PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"
entry = "import site,runpy,sys;site.addsitedir('D:/dianzi/backend/.venv/Lib/site-packages');sys.argv=sys.argv[1:];runpy.run_module(sys.argv[0],run_name='__main__')"
command = [PYTHON, "-c", entry, module, *arguments]
if module == "cbm":
    command = ["C:/Windows/System32/wsl.exe", "-d", "Ubuntu-22.04", "--", "python3",
               "/mnt/d/wt/r18-http-mcp-review1/reports/runs/r18_http_mcp_review1_20261017/cbm_scope.py", *arguments]
exit_code = helper.execute(label, command, timeout=60, process_cap=8 if module == "cbm" else 10)
receipt = {
    "exit_code": exit_code,
    "caller": "/root/r18_http_mcp_first_independent_review",
    "fixture_only": True,
    "memory_per_process_bytes": limits.MEMORY_PER_PROCESS,
    "memory_total_bytes": limits.MEMORY_TOTAL,
    "cpu_rate": limits.CPU_RATE,
    "logical_cpu_count": os.cpu_count(),
    "usage_after": job.usage(),
    "instrument_provenance": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in [HELPER, HELPER.with_name("batch13_process_metadata.py"), LIMITS]},
    "sdk_source_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT / "sdk/python/ai_intel_client").glob("*.py"))},
    "request": "Root ordinary SDK offline narrow window; no PG/WSL/paid; native fixture loopback only under Root ACK",
}
(RUN / (label + ".owned.json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
raise SystemExit(exit_code)

