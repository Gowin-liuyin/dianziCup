"""Seal only the independent review's report and artifacts, with no product mutation."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

from control import ROOT, RUN, SHA, now, private_url, write

started, wall = now(), time.perf_counter()
report = ROOT / "reports/reviews/recovery/G-C-R06-bulk-source-evidence-review-1.md"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
assert subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True) == ""
untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
assert all(path == report.relative_to(ROOT).as_posix() or path.startswith(RUN.relative_to(ROOT).as_posix() + "/") for path in untracked)
assert report.exists()
assert all(line.rstrip() == line for line in report.read_text(encoding="utf-8").splitlines())
raw = Path("D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin").read_bytes()
assert len(raw) == 616865 and hashlib.sha256(raw).hexdigest() == "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"
url = private_url()
for path in sorted(RUN.glob("*.command.json")):
    command = json.loads(path.read_text(encoding="utf-8"))
    assert command["terminated_and_waited"] and not command["timeout"]
for number in ("1", "2"):
    versions = json.loads((RUN / ("replay_" + number + "_script_versions.json")).read_bytes())
    assert hashlib.sha256((RUN / "replay_control_executed_original.py.txt").read_bytes()).hexdigest() == versions["control.py"]
    for name in ("replay", "verify_raw"):
        assert hashlib.sha256((RUN / ("replay_" + number + "_" + name + "_executed.py.txt")).read_bytes()).hexdigest() == versions[name + ".py"]
write("seal_validation.json", {"started_at": started, "validated_at": now(), "validation_wall_seconds": time.perf_counter() - wall, "cwd": str(ROOT), "reviewed_sha": SHA, "source_diff_empty": True, "own_artifact_paths_only": True, "executed_replay_source_hashes_match": True, "raw_body_scan_matches": 0, "credential_scan_matches": 0, "process_exit_claim": "actual exit is recorded by the tool caller; this receipt records completed validation only"})
entries = []
for path in [report, *sorted(RUN.rglob("*"))]:
    if not path.is_file() or path.name == "artifact_manifest.json" or "__pycache__" in path.parts:
        continue
    content = path.read_bytes()
    assert raw not in content and url.password.encode() not in content
    assert url.render_as_string(hide_password=False).encode() not in content
    entries.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
audit = json.loads((RUN / "audit_final_receipt.json").read_bytes())
write("artifact_manifest.json", {"sealed_at": now(), "reviewed_sha": SHA, "reviewed_tree": "25bcfe534c447b5b83d4bceed9b1393cfb266109", "author_material_commit": "bdebeca358f0cfd63630b223dee64647b5280687", "report": {"path": report.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(report.read_bytes()).hexdigest()}, "scope": "independent review and own probes only; limited service Ship; no accepted/progress/product change", "actual_raw_handlers": 2, "replay_total_wall_seconds_all_provisioning_included": audit["replay_total_controller_wall_seconds"], "raw_external_sha256": hashlib.sha256(raw).hexdigest(), "raw_external_bytes": len(raw), "test_counts": audit["tests"], "files": entries, "manifest_excludes_itself": True, "raw_body_in_repository": False, "credential_scan_matches": 0, "source_diff_empty": True})
manifest = RUN / "artifact_manifest.json"
print(json.dumps({"report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "files": len(entries), "reviewed_sha": SHA}, ensure_ascii=False))
