"""复跑集成切片，保存真实退出码、原日志与独立 JUnit 计数。"""

import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as element_tree
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
mode = sys.argv[1]
assert mode in {"source", "sdk"}
suffix = sys.argv[2] if len(sys.argv) > 2 else ""
assert suffix in {"", "_fix1"}
environment = os.environ.copy()
for name in tuple(environment):
    if name.startswith(("GENERATION_", "DEEPSEEK_", "FOFA_", "HUNTER_", "QUAKE_", "ZOOMEYE_", "LANGSMITH_", "LANGCHAIN_")) or name == "TEST_DATABASE_URL":
        environment.pop(name)
environment.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", TIKTOKEN_CACHE_DIR="D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016")
environment["PYTHONPATH"] = str(ROOT / ("backend/src" if mode == "source" else "sdk/python"))
if mode == "source":
    files = ["tests/unit/test_r06_source_excerpt_event_proof.py", "tests/unit/test_r04_source_documents.py", "tests/unit/test_r06_source_catalog.py", "tests/unit/test_r07_public_signals.py", "tests/unit/test_r07_public_signals_fix1.py", "tests/contract/test_r07_public_signals_fix1_cwe.py", "tests/contract/test_t09_document_parsing.py", "tests/contract/test_r10_graph_contract.py", "tests/unit/test_r10_evidence_graph.py", "tests/security/test_r10_graph_boundary.py", "tests/unit/test_r04_source_jobs.py", "tests/unit/test_r06_source_worker.py", "tests/unit/test_r06_source_polling.py", "tests/unit/test_r06_source_boundary_regressions.py", "tests/unit/test_r06_live_source_compatibility.py", "tests/unit/test_r06_osv_range_boundaries.py", "tests/contract/test_t12_vendor_blog_connectors.py", "tests/contract/test_t13_community_repository_connectors.py", "tests/contract/test_t14_academic_connector.py", "tests/contract/test_t15_standards_policy_connectors.py"]
    cwd = ROOT / "backend"
else:
    files = ["sdk/python/tests", "backend/tests/contract/test_r18_public_extensions.py"]
    cwd = ROOT
    environment["SDK_TEST_EVIDENCE_DIR"] = str(RUN / "sdk_batch5_observations")
xml_path = RUN / (mode + "_batch5" + suffix + ".xml")
assert not xml_path.exists()
command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", *files, "--junitxml=" + str(xml_path)]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
monotonic_started = time.monotonic()
result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=180, check=False)
output = result.stdout + result.stderr
(RUN / (mode + "_batch5" + suffix + ".log")).write_bytes(output)
cases = element_tree.parse(xml_path).findall(".//testcase") if xml_path.exists() else []
counts = {"total": len(cases), "failed": sum(case.find("failure") is not None for case in cases), "errors": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)}
counts["passed"] = counts["total"] - counts["failed"] - counts["errors"] - counts["skipped"]
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "duration_seconds": time.monotonic() - monotonic_started, "command": command, "cwd": str(cwd), "exit_code": result.returncode, "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "worktree_source_receipt": "reviewed_source_sdk_batch5.json", "counts": counts, "log_sha256": hashlib.sha256(output).hexdigest(), "live": "not_run", "full_repository_checks": "not_run"}
(RUN / (mode + "_batch5" + suffix + ".json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
raise SystemExit(result.returncode)
