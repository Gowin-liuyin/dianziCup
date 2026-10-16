"""集成安全分类复核的五个完整输入，保留旧登记和全部原始字节。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
AUTHOR = Path("D:/wt/r20-secret-provenance-fix1")
SOURCE = "3b2fc48bb16afd5fea78520e55830b1ffb5d43b1"
MANIFEST = AUTHOR / "reports/runs/recovery_r20_secret_provenance_fix1_20261016/artifact_manifest.json"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip()
raw_manifest = MANIFEST.read_bytes()
assert hashlib.sha256(raw_manifest).hexdigest() == "f03a1f964eece0232afed560778696d86b404e009ab8b95ac3a06fbef218bfc3"
manifest = json.loads(raw_manifest)
assert manifest["source_sha"] == SOURCE and len(manifest["source_files"]) == 5
old_registry = ROOT / "reports/security/recovery_fixture_false_positives.json"
old_raw = old_registry.read_bytes()
assert hashlib.sha256(old_raw).hexdigest() == "ffdf1889362dfaa6de120cc27a77769b719d978779035d8a9f797a2abc06236e"
entries = []
for item in manifest["source_files"]:
    relative = item["path"]
    assert not subprocess.check_output(["git", "diff", "--", relative], cwd=ROOT).strip()
    target = ROOT / relative
    raw = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=AUTHOR)
    if relative.endswith("recovery_fixture_false_positives.json"):
        original = json.loads(old_raw)
        revised = json.loads(raw)
        assert original["records"] == revised["records"][:54]
        assert len(revised["records"]) == 136
    elif target.exists():
        assert target.read_bytes() == raw, "existing different input: " + relative
    assert subprocess.check_output(["git", "rev-parse", SOURCE + ":" + relative], cwd=AUTHOR, text=True).strip() == item["git_blob"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    entries.append({"path": relative, "git_blob": item["git_blob"], "git_raw_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_sha": SOURCE, "review_material_sha": "c9db0d339663c8928e3c1e33a3bc0333152857f4", "complete_input_manifest": entries, "old_54_records_unchanged": True, "record_count": 136, "tests": "not_run", "stage_gate": "not_accepted"}
(RUN / "secret_registry_batch6.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files_integrated": len(entries), "record_count": 136, "old_54_records_unchanged": True}))
