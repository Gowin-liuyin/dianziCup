"""实际写报告时间与最终raw材料hash，manifest不自引用；不更改业务或已有测试。"""

import gzip
import hashlib
import json
import subprocess
import sys
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
    raw = REPORT.read_bytes()
    assert b"0892b6af7fbc0c16651aeb25f14493fb4c3fa48d" in raw
    stamp = (
        "\n最终报告写入时间："
        + started.isoformat(timespec="seconds")
        + "；首次正文创建未单独分秒计时，本记录仅是实际最终装订写入。\n"
    )
    REPORT.write_bytes(raw + stamp.encode())
    filtered = (
        subprocess.run(
            ["git", "hash-object", "--path", "reports/tasks/R11-sbom-inventory.md", str(REPORT)],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    receipt = {
        "start": started.isoformat(timespec="seconds"),
        "end": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "scope": "final_report_write_initial_creation_not_separately_timed",
        "raw_report_sha256": sha(REPORT.read_bytes()),
        "git_filtered_report_blob": filtered,
        "body_hash": None,
        "code_commit": "0892b6af7fbc0c16651aeb25f14493fb4c3fa48d",
        "material_commit": None,
        "argv": [sys.executable, str(Path(__file__).resolve())],
    }
    (RUN / "report_write_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    records = []
    excluded = {"artifact_manifest.json", "seal_receipt.json"}
    paths = [REPORT, *(path for path in sorted(RUN.rglob("*")) if path.is_file())]
    for path in paths:
        if path.name in excluded or "__pycache__" in path.parts:
            continue
        content = path.read_bytes()
        record = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(content),
            "sha256": sha(content),
        }
        if path.suffix == ".gz":
            uncompressed = gzip.decompress(content)
            record["gzip_raw_sha256"] = sha(uncompressed)
            record["gzip_raw_bytes"] = len(uncompressed)
        records.append(record)
    manifest = {
        "code_commit": receipt["code_commit"],
        "material_commit": None,
        "report_path": "reports/tasks/R11-sbom-inventory.md",
        "entries": records,
    }
    manifest_path = RUN / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for record in records:
        assert sha((ROOT / record["path"]).read_bytes()) == record["sha256"]
    seal = {
        "manifest_sha256": sha(manifest_path.read_bytes()),
        "files": len(records),
        "finished_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "all_raw_bytes_verified": True,
        "material_commit": None,
        "note": "commit supplied separately by actual git result; no invented self hash",
    }
    (RUN / "seal_receipt.json").write_text(
        json.dumps(seal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(seal))


if __name__ == "__main__":
    main()
