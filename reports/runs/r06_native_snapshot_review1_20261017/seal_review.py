"""Seal this review's public evidence and check its unchanged source-only scope."""

import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-native-snapshot-review-1.md"
SOURCE_RUN = ROOT / "reports/runs/r06_native_process_snapshot_20261017"
manifest = json.loads((SOURCE_RUN / "handoff/source_manifest.json").read_bytes())
scope_checks = []
for row in manifest["source_23"]:
    if row["component"] not in {"core", "ops"}:
        continue
    path = RUN / "cbm_scope" / row["component"] / Path(row["candidate_path"]).name
    assert path.read_bytes() == (ROOT / row["candidate_path"]).read_bytes()
    scope_checks.append({"path": str(path.relative_to(RUN)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
assert len(scope_checks) == 20
(RUN / "cbm_scope.pending.json").write_text(json.dumps({
    "status": "prepared_not_indexed", "source_material": "a70e653a92771b6c077bbda8a8263721f83a55a5",
    "scope_files": scope_checks, "private_or_holdout_indexed": False,
    "planned_fresh_cache": "/tmp/dianzi-cbm-r06-native-review1-20261017",
    "cache_created": False, "index_schema_trace_resource_coverage": "not_run",
    "reason": "fixed candidate has independently reproduced blocking bound-generation failures",
}, indent=2) + "\n", encoding="utf-8")
(RUN / "root_window_authorizations.json").write_text(json.dumps({
    "authorized_before_original7": "现在批准两个连续但各自独立≤20s native窗（内部15s）；先原7，再root-child-grandchild 3 held ACK，与原出生Job门一致；每窗结束确认资源交回再开始。Root期间只做读/文档，不跑重Node类型，R10 PG矩阵仍有单2CPU job但无native Windows批。源服务/installed/private/binding不授权；结束给真实diff/scene与未验，不能署actual Root17 audit通过。",
    "authorized_before_detached_retry": "批准仅自有三dummy创建flag DETACHED_PROCESS0x8、保持PIPE/真实Popen+held births/Job门及cap10，原CREATE_NO_WINDOW峰11红保留。单≤20s重试多代一次，不重源逻辑。unknownbirth类型偏差请作为合同差异留报告：Root会要求作者小fix统一OwnershipError，不能口头改CR迁就代码；当前c8 native证据保持其版本，复核新的helper差异后追加必要负例即可。",
    "ack_timestamp_not_in_message": True, "actual_execution_times": "separate command receipts",
    "all_three_windows_released_to_root": True,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
syntax = []
for name in ("run_owned.py", "native_probe.py", "native_multigeneration.py", "native_multigeneration_first.py", "test_review_unknown_bound_birth.py", "verify_fixed.py", "seal_review.py"):
    ast.parse((RUN / name).read_text(encoding="utf-8"), filename=name)
    syntax.append(name)
cases = []
counts = {}
for label in ("offline_new38", "offline_original74", "offline_prior60", "unknown_bound_contract"):
    items = ET.parse(RUN / (label + ".xml")).getroot().findall(".//testcase")
    counts[label] = {"tests": len(items), "failed": sum(item.find("failure") is not None for item in items), "errors": sum(item.find("error") is not None for item in items), "skipped": sum(item.find("skipped") is not None for item in items)}
    cases.extend((item.get("classname"), item.get("name")) for item in items)
assert len(cases) == len(set(cases)) == 176
source_diff = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", "reports/runs/recovery_r06_activation_prep_20261016/candidate"], cwd=ROOT, capture_output=True, check=True)
assert not source_diff.stdout
source_check = subprocess.run(["git", "diff", "--check", "HEAD", "--", "reports/runs/recovery_r06_activation_prep_20261016/candidate"], cwd=ROOT, capture_output=True)
assert source_check.returncode == 0
terminal = {
    "observed_at": datetime.now(timezone.utc).isoformat(), "verdict": "needs_changes",
    "candidate_tracked_diff": [], "candidate_diff_check_exit_code": source_check.returncode,
    "own_python_ast_parse_files": syntax, "counts": counts,
    "distinct_pytest_cases": len(set(cases)), "native_original7": "passed",
    "native_multigeneration_first_resource_gate": "failed_peak_11",
    "native_multigeneration_detached": "passed_peak_8_three_held_exit70_acks",
    "cbm": "prepared_not_indexed_partial", "root_actual_audit_install_seven_gates_source_six_hours": "not_run",
    "report": str(REPORT), "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
}
(RUN / "terminal_checks.json").write_text(json.dumps(terminal, indent=2) + "\n", encoding="utf-8")
rows = []
for path in sorted(RUN.rglob("*")):
    if not path.is_file() or path.name == "artifact_manifest.json":
        continue
    rows.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
(RUN / "artifact_manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "fixed_material": "a70e653a92771b6c077bbda8a8263721f83a55a5", "files": rows, "report_sha256": terminal["report_sha256"]}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": "needs_changes", "distinct_pytest_cases": len(set(cases)), "scope_files": len(scope_checks), "evidence_files": len(rows), "candidate_diff_check_exit": source_check.returncode}))
