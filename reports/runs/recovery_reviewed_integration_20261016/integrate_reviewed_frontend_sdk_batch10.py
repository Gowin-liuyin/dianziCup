"""Import exact independently reviewed feature and SDK sources without older package files."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def blob(sha, relative):
    return subprocess.check_output(["git", "show", sha + ":" + relative], cwd=ROOT)


started = clock()
baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
if protected_hash != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user file changed")
sdk = "40b2d07bfd9047e38698339eb18a4f1e31a32153"
models = "011ea225d18b7511a19d7d6056288f799bb83f20"
frontend = "da43a8919a24119406b68fb16e1e3a344205d7c7"
model_path = "sdk/python/ai_intel_client/models.py"
if blob(sdk, model_path) != blob(models, model_path):
    raise RuntimeError("six-tool SDK models differ from the independently reviewed qualification fix")
sources = {
    "sdk/python/ai_intel_client/__init__.py": sdk,
    "sdk/python/ai_intel_client/client.py": sdk,
    "sdk/python/ai_intel_client/mcp_adapter.py": sdk,
    model_path: models,
    "sdk/python/tests/test_six_read_tools.py": sdk,
    "sdk/python/tests/test_public_extension_models.py": models,
    "sdk/python/tests/test_public_extension_models_fix1.py": models,
}
feature_paths = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", frontend, "frontend/src/features/investigations"],
    cwd=ROOT, text=True,
).splitlines()
if len(feature_paths) != 9:
    raise RuntimeError("unexpected reviewed investigation feature closure")
sources.update(dict.fromkeys(feature_paths, frontend))
prepared = []
for relative, sha in sources.items():
    target = ROOT / relative
    before = target.read_bytes() if target.exists() else None
    tracked = subprocess.run(["git", "show", baseline + ":" + relative], cwd=ROOT, capture_output=True)
    if before is not None:
        if tracked.returncode:
            raise RuntimeError("existing untracked feature input; refusing overwrite: " + relative)
        if before.replace(b"\r\n", b"\n") != tracked.stdout.replace(b"\r\n", b"\n"):
            raise RuntimeError("existing working edits; refusing overwrite: " + relative)
    raw = blob(sha, relative)
    prepared.append((target, raw, {"path": relative, "source_sha": sha, "raw_sha256": hashlib.sha256(raw).hexdigest(), "before_raw_sha256": hashlib.sha256(before).hexdigest() if before is not None else None, "bytes": len(raw)}))
for target, raw, _ in prepared:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
receipt = {
    "started_at": started, "ended_at": clock(), "baseline_sha": baseline,
    "files": [record for _, _, record in prepared], "package_metadata_preserved": True,
    "independent_reviews": {
        "sdk_six": "e7213d6a786e118823101dac52d5549fe48ddad6",
        "model_qualification": "336652179a2ba57937913ef83e1917287d6e2705",
        "frontend_revision_fix": "02c1c352c68b90737482decb821138c4d9fe92cc",
    },
    "protected_user_file_sha256": protected_hash,
    "root_app_mount": "not_yet_changed; requires its own integration review",
    "whole_tasks_accepted": False,
}
(RUN / "reviewed_frontend_sdk_batch10_inputs.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files": len(prepared), "baseline_sha": baseline, "package_metadata_preserved": True}))
