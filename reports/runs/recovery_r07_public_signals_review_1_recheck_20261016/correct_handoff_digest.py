"""Keep the failed assertion and distinguish corrected file-list and manifest-byte digests."""

import hashlib
import json
import subprocess

from run_commands import CODE, MATERIAL, ROOT, RUN, SOURCE_PATHS, timestamp

started = timestamp()
path = "reports/runs/recovery_r07_public_signals_fix1_20261016/artifact_manifest.json"
raw = subprocess.check_output(["git", "show", MATERIAL + ":" + path], cwd=ROOT)
manifest = json.loads(raw)
filelist_digest = hashlib.sha256(json.dumps(manifest["material_files"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
assert filelist_digest == manifest["filelist_sha256"] == "a3ea1549f82c7dd714418046703b20424445ca5ac79265b287d85d4c081bee06"
assert hashlib.sha256(raw).hexdigest() == "91125322b8fa70d7c5dd9c40af8f84ad1afcd56c6070316af8dddb32094885dd"
unchanged = {}
for source in (SOURCE_PATHS[1], SOURCE_PATHS[2], SOURCE_PATHS[3], SOURCE_PATHS[6], SOURCE_PATHS[7]):
    previous = subprocess.check_output(["git", "show", "7f8cdc81108e39819d192c09bf1b4a61c640aec9:" + source], cwd=ROOT)
    current = subprocess.check_output(["git", "show", MATERIAL + ":" + source], cwd=ROOT)
    assert previous == current
    unchanged[source] = hashlib.sha256(current).hexdigest()
result = {"started_at": started, "ended_at": timestamp(), "material_sha": MATERIAL, "code_sha": CODE,
          "manifest_bytes": len(raw), "manifest_bytes_sha256": hashlib.sha256(raw).hexdigest(),
          "filelist_sha256": filelist_digest, "filelist_recomputed": True,
          "root_correction": "Root confirmed 144509-byte manifest with git and author worktree; a3ea is top-level filelist_sha256, not manifest-byte SHA. Root handoff naming confusion corrected; original strict exit1 remains.",
          "unchanged_prior_source_contracts_and_tests": unchanged,
          "business_findings": "Two original Must triggers and their related positive/negative checks passed independently",
          "instrumentation_notes": ["Exploratory checks.py lookup was absent; actual run_commands.py read next",
                                    "Literal Windows *.py rg path failed; corrected to rg -g '*.py' against directory"],
          "new_network_calls": 0, "new_model_calls": 0, "pg_calls": 0}
(RUN / "handoff_digest_correction.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"manifest_bytes_sha256": result["manifest_bytes_sha256"], "filelist_sha256": filelist_digest,
                  "filelist_recomputed": True, "unchanged_prior_files": len(unchanged)}))
