"""Archive immutable reports while keeping public token-shaped HTML originals outside Git."""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.security_scan import PATTERNS

ROOT = Path(__file__).resolve().parents[3]
RECEIPTS = []
for suffix, expected in (
    ("recheck", "97875a0d9f739058e82b4fd44a55eef355a021d26795b086ac03711cdcf31a19"),
    ("recheck2", "431b50451b1e0c6540c7e44dbb1a6cd4868938688fc504a8e2179da9c224e9ac"),
):
    source = Path("D:/wt/r06-source-worker-review-1-" + suffix)
    run_name = "recovery_r06_source_worker_review_1_" + suffix + "_20261015"
    manifest_path = Path("reports/runs") / run_name / "evidence_manifest.json"
    report_path = Path("reports/reviews/recovery/G-C-R06-source-worker-review-1-" + suffix + ".md")
    original_manifest = (source / manifest_path).read_bytes()
    assert hashlib.sha256(original_manifest).hexdigest() == expected
    manifest = json.loads(original_manifest)
    copied = []
    outside = []
    for item in manifest["artifact_files"]:
        relative = Path(item["path"])
        assert relative.as_posix().startswith("reports/runs/" + run_name + "/") or relative == report_path
        assert not any(part in {"__pycache__", "mypy_cache", "cbm_cache"} for part in relative.parts)
        original = source / relative
        raw = original.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if original.suffix == ".html" and any(
            pattern.search(raw.decode("utf-8", errors="ignore")) for pattern in PATTERNS.values()
        ):
            cache = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-review-sensitive-originals") / run_name
            cache.mkdir(parents=True, exist_ok=True)
            retained = cache / relative.name
            if retained.exists():
                assert retained.read_bytes() == raw
            else:
                shutil.copyfile(original, retained)
            content = raw.decode("utf-8")
            for match in reversed(list(PATTERNS["original_secret_value_pattern"].finditer(content))):
                content = content[:match.start(2)] + content[match.end(2):]
            derivative = target.with_suffix(".redacted.html")
            derivative.write_text(content, encoding="utf-8")
            outside.append({"original_relative_path": relative.as_posix(), "original_sha256": item["sha256"], "outside_path": str(retained), "derivative": derivative.relative_to(ROOT).as_posix(), "derivative_sha256": hashlib.sha256(derivative.read_bytes()).hexdigest()})
            continue
        if target.exists():
            assert target.read_bytes() == raw
        else:
            shutil.copyfile(original, target)
        copied.append(relative.as_posix())
    target = ROOT / manifest_path
    if target.exists():
        assert target.read_bytes() == original_manifest
    else:
        shutil.copyfile(source / manifest_path, target)
    assert hashlib.sha256((source / report_path).read_bytes()).hexdigest() == manifest["report_sha256"]
    shutil.copyfile(source / report_path, ROOT / report_path)
    RECEIPTS.append({"manifest": manifest_path.as_posix(), "manifest_sha256": expected, "verified_members": len(manifest["artifact_files"]), "copied_members": len(copied), "outside_originals": outside, "report": report_path.as_posix(), "report_sha256": manifest["report_sha256"]})

Path(__file__).with_name("source_rechecks_archive_receipt.json").write_text(json.dumps({"at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "original_manifests_unchanged": True, "initial_allowlist_rejected_own_report_then_corrected": True, "packages": RECEIPTS}, indent=2) + "\n", encoding="utf-8")
print(json.dumps([{"verified": receipt["verified_members"], "copied": receipt["copied_members"], "outside": len(receipt["outside_originals"])} for receipt in RECEIPTS]))
