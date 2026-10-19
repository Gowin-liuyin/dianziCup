"""Verify the author's fixed manifest against exact Git blob bytes and preserve original probes."""

import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree

from run_commands import CODE, MATERIAL, ROOT, RUN, SOURCE_PATHS, timestamp

started = timestamp()
manifest_path = "reports/runs/recovery_r07_public_signals_fix1_20261016/artifact_manifest.json"
manifest_bytes = subprocess.check_output(["git", "show", MATERIAL + ":" + manifest_path], cwd=ROOT)
provided_manifest_sha256 = "a3ea1549f82c7dd714418046703b20424445ca5ac79265b287d85d4c081bee06"
manifest = json.loads(manifest_bytes)
assert len(manifest["material_files"]) == 100
verified = []
for item in manifest["material_files"]:
    raw = subprocess.check_output(["git", "show", MATERIAL + ":" + item["path"]], cwd=ROOT)
    digest = hashlib.sha256(raw).hexdigest()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert len(raw) == item["bytes"] and digest == item["sha256"] and blob == item["git_blob_exact_bytes"]
    working = (ROOT / item["path"]).read_bytes()
    verified.append({"path": item["path"], "bytes": len(raw), "sha256": digest, "git_blob": blob,
                     "working_bytes_equal_git_blob": working == raw})
inputs = {}
for path in SOURCE_PATHS:
    blob = subprocess.check_output(["git", "show", MATERIAL + ":" + path], cwd=ROOT)
    code_blob = subprocess.check_output(["git", "show", CODE + ":" + path], cwd=ROOT)
    assert blob == code_blob
    inputs[path] = {"git_bytes_sha256": hashlib.sha256(blob).hexdigest(),
                    "working_bytes_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                    "working_lf_sha256": hashlib.sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                    "material_and_code_equal": True}
previous = Path("D:/wt/r07-public-signals-review-1/reports/runs/recovery_r07_public_signals_review_1_20261016")
previous_manifest = json.loads((previous / "artifact_manifest.json").read_bytes())
for filename in ("test_independent_boundaries.py", "replay_public_bodies.py"):
    raw = (previous / filename).read_bytes()
    prior = next(item for item in previous_manifest["artifacts"] if item["path"].endswith("/" + filename))
    assert hashlib.sha256(raw).hexdigest() == prior["sha256"]
    (RUN / filename).write_bytes(raw)
old_red = ElementTree.parse(previous / "independent_boundaries_v2.xml").getroot()[0]
assert int(old_red.get("tests")) == 23 and int(old_red.get("failures")) == 2
old_log = previous / "independent_boundaries_v2.log"
assert "2 failed, 21 passed" in old_log.read_text(encoding="utf-8")
originals = {}
author_run = ROOT / "reports/runs/recovery_r07_public_signals_fix1_20261016"
for receipt_name in ("original_red", "new_red", "focused_frozen", "regression_frozen",
                     "original_recheck_frozen", "new_regression_frozen", "new_green"):
    path = author_run / (receipt_name + ".command.json")
    if path.exists():
        receipt = json.loads(path.read_bytes())
        originals[receipt_name] = {key: receipt.get(key) for key in ("exit_code", "started_at", "ended_at", "head", "candidate_sha", "argv")}
result = {"started_at": started, "ended_at": timestamp(), "candidate_sha": MATERIAL, "code_sha": CODE,
          "manifest_path": manifest_path, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
          "provided_manifest_sha256": provided_manifest_sha256,
          "provided_hash_matches": hashlib.sha256(manifest_bytes).hexdigest() == provided_manifest_sha256,
          "manifest_plus_material_files_verified": 101, "material_files": verified,
          "working_byte_differences": [item["path"] for item in verified if not item["working_bytes_equal_git_blob"]],
          "inputs": inputs, "original_independent_red": "23 tests, 2 failed, 21 passed; originals preserved in original independent worktree",
          "author_receipt_observations": originals}
(RUN / "author_material_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"manifest_sha256": result["manifest_sha256"], "verified": 101,
                  "working_byte_difference_count": len(result["working_byte_differences"]),
                  "original_independent_script_copied_unchanged": True}))
