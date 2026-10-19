"""Seal the fixed review without replacing any initial-review evidence."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-native-snapshot-review-1.md"
MANIFEST = ROOT / "reports/runs/r06_native_process_snapshot_bound_fix2_20261017/handoff/source_manifest.json"
manifest = json.loads(MANIFEST.read_bytes())
assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == "6a1f1cccb510dffe00fa379166d2f423731baf67fa124853493d3b347f80ba55"
assert hashlib.sha256((RUN / "test_review_unknown_bound_birth.py").read_bytes()).hexdigest() == "62ce26870a41a0821d3db16137f75cb0a02f899aaf4928a4c1b5c91d2b5bac87"
scope = []
for item in manifest["source_23"]:
    if item["component"] not in {"core", "ops"}:
        continue
    path = RUN / "cbm_scope_fix2" / item["component"] / Path(item["candidate_path"]).name
    assert path.read_bytes() == (ROOT / item["candidate_path"]).read_bytes()
    scope.append({"path": str(path.relative_to(RUN)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
assert len(scope) == 20
counts = {}
for label in ("fix2_original_negative4", "fix2_author54"):
    cases = ET.parse(RUN / (label + ".xml")).getroot().findall(".//testcase")
    assert all(item.find("failure") is None and item.find("error") is None and item.find("skipped") is None for item in cases)
    counts[label] = len(cases)
guest_results = json.loads((RUN / "fix2_cbm_results.json").read_bytes())
control = json.loads((RUN / "cbm_resource_control.json").read_bytes())
assert control["tool_root_is_pid1"] is False and control["ancestors"][0]["pid"] != 1
guest_termination = []
for identity in [control["ancestors"][0], *[item["child_identity"] for item in guest_results["results"]]]:
    path = Path(r"\\wsl.localhost\Ubuntu-22.04\proc") / str(identity["pid"]) / "stat"
    if not path.exists():
        state = "absent"
    else:
        raw = path.read_text()
        birth = int(raw.rsplit(")", 1)[1].split()[19])
        state = "different_generation" if birth != identity["birth_clock_ticks"] else "same_generation_present"
    assert state != "same_generation_present"
    guest_termination.append({**identity, "state": state})
source_diff = subprocess.check_output(["git", "diff", "--name-only", "HEAD", "--", "reports/runs/recovery_r06_activation_prep_20261016/candidate"], cwd=ROOT)
assert not source_diff
check = subprocess.run(["git", "diff", "--check", "HEAD", "--", "reports/runs/recovery_r06_activation_prep_20261016/candidate"], cwd=ROOT)
assert check.returncode == 0
result = {
    "observed_at": datetime.now(timezone.utc).isoformat(), "verdict": "LimitedShip",
    "material_sha": "f4036d3ab38cc7999d1b50bc335e47a4b7fdcd96",
    "core_sha": "37ffe6da1d9a258359363d42488d236b7c00ad87", "ops_sha": "81053fd680dbfb275bfcc511ae44f573340efd56",
    "source_manifest_raw_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
    "pending_runtime_hash": "9be80e1c0bbed25c2cdcb352d5b38158d01d127e929a290500dbf0576f99287a",
    "counts": counts, "native_seven": "passed_after_original_timeout_preserved", "native_multigeneration": "passed_in_independent_window_after_combined_ready_failure_preserved",
    "cbm_guest_terminal": guest_termination, "cbm_scope": scope,
    "cbm_index_nodes": 307, "cbm_index_edges": 1422, "cbm_parse_partial": 1,
    "cbm_guest_hard_memory_cap": "not_verified", "pipe_scenario": "not_run",
    "actual_audit_installation_source_six_hours": "not_run", "new_audit_helper_review": "pending_fixed_material",
    "candidate_tracked_diff": [], "candidate_diff_check_exit": check.returncode,
    "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
}
(RUN / "fix2_terminal_checks.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
rows = []
for path in sorted(RUN.rglob("*")):
    if path.is_file() and path.name != "artifact_manifest_fix2.json":
        raw = path.read_bytes()
        rows.append({"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
(RUN / "artifact_manifest_fix2.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "material_sha": result["material_sha"], "report_sha256": result["report_sha256"], "files": rows}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": result["verdict"], "original4": counts["fix2_original_negative4"], "author54": counts["fix2_author54"], "guest_same_generation_remaining": 0, "report_sha256": result["report_sha256"]}))
