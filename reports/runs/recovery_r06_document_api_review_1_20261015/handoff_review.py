"""Copy only owned review artifacts to the controller tree and verify bytes."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from review_runner import ROOT, RUN, now

TARGET = Path("D:/dianzi")
REPORT = Path("reports/reviews/recovery/G-C-R06-document-api-review-1.md")
started = now()
subprocess.run([sys.executable, str(RUN / "seal_review.py")], check=True)
manifest_path = RUN / "artifact_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
paths = [Path(member["path"]) for member in manifest["files"]] + [REPORT]
for relative in paths:
    source = ROOT / relative
    destination = TARGET / relative
    raw = source.read_bytes()
    if destination.exists() and destination.read_bytes() != raw:
        raise RuntimeError("destination contains different bytes: " + str(relative))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    assert destination.read_bytes() == raw
report_raw = (ROOT / REPORT).read_bytes()
receipt = {
    "argv": [sys.executable, str(Path(__file__))], "cwd": str(ROOT),
    "started_at": started, "ended_at": now(), "exit_code": 0,
    "destination": str(TARGET), "verified_members_before_receipt_and_manifest": len(paths),
    "report": str(REPORT).replace("\\", "/"),
    "report_bytes": len(report_raw), "report_sha256": hashlib.sha256(report_raw).hexdigest(),
    "verification": "every copied owned file byte-for-byte; destination differences fail closed",
}
receipt_path = RUN / "handoff.command.json"
receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
raw = receipt_path.read_bytes()
manifest["files"].append({"path": str(receipt_path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
manifest["created_at"] = now()
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
for source in (receipt_path, manifest_path):
    destination = TARGET / source.relative_to(ROOT)
    destination.write_bytes(source.read_bytes())
    assert destination.read_bytes() == source.read_bytes()
for member in manifest["files"]:
    raw = (TARGET / member["path"]).read_bytes()
    assert len(raw) == member["bytes"] and hashlib.sha256(raw).hexdigest() == member["sha256"]
print(json.dumps({"report_sha256": receipt["report_sha256"], "raw_manifest_members": len(manifest["files"]), "copy_verified": True}))
