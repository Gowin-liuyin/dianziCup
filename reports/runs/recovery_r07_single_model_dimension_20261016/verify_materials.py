"""Recheck manifest raw and staged bytes without generating further mutable artifacts."""

import hashlib
import json
import subprocess
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent
WORKTREE = RUN_ROOT.parents[2]
manifest_path = RUN_ROOT / "material_manifest.json"
manifest_raw = manifest_path.read_bytes()
manifest = json.loads(manifest_raw)
assert hashlib.sha256(manifest_raw).hexdigest() == (
    RUN_ROOT / "material_manifest.sha256"
).read_text(encoding="ascii").strip()
for record in manifest["artifacts"]:
    raw = (WORKTREE / record["path"]).read_bytes()
    staged = subprocess.check_output(["git", "show", ":" + record["path"]], cwd=WORKTREE)
    assert len(raw) == record["raw_size_bytes"] == record["git_blob_size_bytes"]
    assert hashlib.sha256(raw).hexdigest() == record["raw_sha256"]
    assert hashlib.sha256(staged).hexdigest() == record["git_blob_sha256"]
    assert raw == staged
subprocess.run(
    ["git", "diff", "--exit-code", manifest["code_sha"], "--", "backend/src", "backend/tests"],
    cwd=WORKTREE, check=True,
)
print(json.dumps({"artifacts_verified": len(manifest["artifacts"]), "source_unchanged": True, "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest()}))
