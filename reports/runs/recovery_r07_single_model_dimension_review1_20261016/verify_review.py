"""Verify every sealed independent artifact and digest without writing new evidence."""

import hashlib
import json

from review_run import ROOT, RUN

raw = (RUN / "review_manifest.json").read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert (RUN / "review_manifest.sha256").read_text().split()[0] == digest
manifest = json.loads(raw)
assert manifest["artifact_count"] == len(manifest["artifacts"])
for entry in manifest["artifacts"]:
    actual = (ROOT / entry["path"]).read_bytes()
    assert len(actual) == entry["raw_size_bytes"], entry["path"]
    assert hashlib.sha256(actual).hexdigest() == entry["raw_sha256"], entry["path"]
print(json.dumps({"verified_artifact_count": manifest["artifact_count"], "manifest_sha256": digest,
                  "material_sha": manifest["material_sha"], "code_sha": manifest["code_sha"]}))
