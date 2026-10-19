"""封存后逐原字节核对，单独回执避免循环引用。"""

import hashlib
import json
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
manifest_path = RUN / "artifact_manifest.json"
manifest = json.loads(manifest_path.read_bytes())
body = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
sidecar = (RUN / "artifact_manifest.sha256").read_text(encoding="ascii").split()[0]
assert body == sidecar
bad = [item["path"] for item in manifest["artifacts"] if hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() != item["sha256"] or (ROOT / item["path"]).stat().st_size != item["bytes"]]
assert not bad
assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True)
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True)
print(json.dumps({"manifest_sha256": body, "verified_artifacts": len(manifest["artifacts"]), "bad": bad, "report_path": manifest["review_path"], "tracked_diff_empty": True}, ensure_ascii=False))
