"""Verify every material staged blob preserves its working bytes and the manifest is exact."""

import hashlib
import json

from run_checks import ROOT, RUN, git

staged = git("diff", "--cached", "--name-only", "-z").decode().split("\0")
for path in filter(None, staged):
    assert git("show", ":" + path) == (ROOT / path).read_bytes(), path
manifest = json.loads((RUN / "artifact_manifest.json").read_text())
for item in manifest["artifacts"]:
    content = (ROOT / item["path"]).read_bytes()
    assert len(content) == item["bytes"]
    assert hashlib.sha256(content).hexdigest() == item["sha256"], item["path"]
    assert hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest() == item["git_raw_blob"]
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "contracts").strip()
print(json.dumps({"staged_material_blobs_exact": len(list(filter(None, staged))), "manifest_artifacts_verified": len(manifest["artifacts"]), "product_tree": "clean"}))
