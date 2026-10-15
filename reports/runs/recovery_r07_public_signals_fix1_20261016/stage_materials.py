"""Stage only this fix's materials without newline conversion and verify every exact Git blob."""

import hashlib
import json
import subprocess
import sys

from run_commands import ROOT, RUN, timestamp
from seal_artifacts import REPORT

started = timestamp()
argv = ["git", "-c", "core.autocrlf=false", "add", "--", RUN.relative_to(ROOT).as_posix(),
        REPORT.relative_to(ROOT).as_posix()]
completed = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False)
assert completed.returncode == 0
verified = []
for path in sorted((*RUN.rglob("*"), REPORT)):
    if not path.is_file() or "__pycache__" in path.parts:
        continue
    relative = path.relative_to(ROOT).as_posix()
    raw = path.read_bytes()
    staged = subprocess.check_output(["git", "show", ":" + relative], cwd=ROOT)
    assert staged == raw, relative
    verified.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                     "git_blob": subprocess.check_output(["git", "rev-parse", ":" + relative],
                                                         cwd=ROOT, text=True).strip(),
                     "exact_bytes_equal": True})
manifest = json.loads((RUN / "artifact_manifest.json").read_bytes())
for record in manifest["material_files"]:
    raw = (ROOT / record["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == record["sha256"], record["path"]
    blob = subprocess.check_output(["git", "rev-parse", ":" + record["path"]], cwd=ROOT, text=True).strip()
    assert blob == record["git_blob_exact_bytes"], record["path"]
receipt = {"started_at": started, "ended_at": timestamp(), "argv": argv, "cwd": str(ROOT),
           "exit_code": completed.returncode, "verified_files": verified,
           "verified_count": len(verified), "manifest_filelist_sha256": manifest["filelist_sha256"],
           "new_network_calls": 0, "new_model_calls": 0, "pg_calls": 0}
if sys.argv[1] == "stage":
    (RUN / "material_staging_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"started_at": started, "ended_at": receipt["ended_at"], "exit_code": 0,
                  "verified_count": len(verified), "exact_bytes_equal": True,
                  "manifest_filelist_sha256": manifest["filelist_sha256"]}))
