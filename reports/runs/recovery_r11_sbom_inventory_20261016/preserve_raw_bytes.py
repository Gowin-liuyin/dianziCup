"""本run独立attributes保留证据raw；报告另存gzip，正文仍按现有Git-LF合同。"""

import gzip
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/tasks/R11-sbom-inventory.md"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    started = datetime.now(ZoneInfo("Asia/Shanghai"))
    report = REPORT.read_bytes()
    compressed = gzip.compress(report, mtime=0)
    assert gzip.decompress(compressed) == report
    (RUN / "report_raw.md.gz").write_bytes(compressed)
    manifest_path = RUN / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    entries = []
    excluded = {"artifact_manifest.json", "seal_receipt.json", "raw_preservation_receipt.json"}
    for path in [REPORT, *(path for path in sorted(RUN.rglob("*")) if path.is_file())]:
        if path.name in excluded or "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        entry = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(raw),
            "sha256": sha(raw),
        }
        if path == REPORT:
            entry["git_lf_sha256"] = sha(raw.replace(b"\r\n", b"\n"))
            entry["exact_raw_copy"] = (
                "reports/runs/recovery_r11_sbom_inventory_20261016/report_raw.md.gz"
            )
        if path.suffix == ".gz":
            uncompressed = gzip.decompress(raw)
            entry["gzip_raw_sha256"] = sha(uncompressed)
            entry["gzip_raw_bytes"] = len(uncompressed)
        entries.append(entry)
    manifest["entries"] = entries
    manifest["raw_preservation"] = "scoped_run_attributes_and_report_gzip"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for entry in entries:
        assert sha((ROOT / entry["path"]).read_bytes()) == entry["sha256"]
        if entry["path"].startswith("reports/runs/"):
            filtered = (
                subprocess.run(
                    ["git", "hash-object", "--path", entry["path"], entry["path"]],
                    cwd=ROOT,
                    capture_output=True,
                    check=True,
                )
                .stdout.decode()
                .strip()
            )
            raw_blob = (
                subprocess.run(
                    ["git", "hash-object", "--no-filters", entry["path"]],
                    cwd=ROOT,
                    capture_output=True,
                    check=True,
                )
                .stdout.decode()
                .strip()
            )
            assert filtered == raw_blob
    receipt = {
        "start": started.isoformat(timespec="seconds"),
        "end": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "files": len(entries),
        "manifest_sha256": sha(manifest_path.read_bytes()),
        "all_raw_bytes_verified": True,
        "all_run_git_filters_preserve_raw": True,
        "scope": "only_this_run_attributes_no_global_attributes_change",
        "report_raw_sha256": sha(report),
        "report_raw_gzip_sha256": sha(compressed),
        "material_commit": None,
    }
    (RUN / "raw_preservation_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (RUN / "seal_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
