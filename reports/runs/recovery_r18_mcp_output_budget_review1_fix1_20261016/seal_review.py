"""Seal the bounded independent recheck report and its raw artifacts."""

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as element_tree
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-E-R18-mcp-output-budget-review-1-recheck.md"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    started = now()
    assert not REPORT.exists()
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip() == (
        "260942efc77168683b2b978747a19c3c9fedce3e"
    )
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT).strip()
    for name, expected in json.loads((RUN / "copied_probe_hashes.json").read_bytes()):
        assert sha((RUN / name).read_bytes()) == expected
    full = element_tree.parse(RUN / "complete_296.xml").getroot()[0].attrib
    controls = element_tree.parse(RUN / "process_control_formatted.xml").getroot()[0].attrib
    assert (full["tests"], full["failures"], full["errors"], full["skipped"]) == (
        "296",
        "0",
        "0",
        "0",
    )
    assert (controls["tests"], controls["failures"], controls["errors"], controls["skipped"]) == (
        "3",
        "0",
        "0",
        "0",
    )
    lines = [
        (RUN / "report_body.md").read_text(encoding="utf-8"),
        "",
        "| 标签 | 实际argv | 开始/结束 +08 | exit | 日志 |",
        "|---|---|---|---|---|",
    ]
    for path in sorted(RUN.glob("*.json")):
        record = json.loads(path.read_bytes())
        if not isinstance(record, dict) or "command" not in record or "exit_code" not in record:
            continue
        command = " ".join(record["command"]).replace("|", "\\|")
        timing = record["started_at"] + " / " + record["finished_at"]
        lines.append(
            f"| {path.stem} | {command} | {timing} | {record['exit_code']} | {record['log_path']} |"
        )
    lines.extend(
        [
            "",
            "报告最终写作开始：" + started + "；写作结束/更新时间/证据截止：" + now() + "。",
            "交互读取及逐次编辑未逐次采集起止，未按mtime推算。",
            "",
        ]
    )
    REPORT.write_bytes("\n".join(lines).encode("utf-8"))
    excluded = {"artifact_manifest.json", "seal_receipt.json"}
    members = sorted(
        path for path in RUN.rglob("*") if path.is_file() and path.name not in excluded
    )
    members.append(REPORT)
    entries = []
    for path in members:
        raw = path.read_bytes()
        exact = path.suffix in {".log", ".xml", ".raw"}
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": len(raw),
                "raw_sha256": sha(raw),
                "git_byte_mode": "exact_raw" if exact else "LF",
                "git_blob_sha256": sha(raw if exact else raw.replace(b"\r\n", b"\n")),
            }
        )
    manifest = {
        "sealed_at": now(),
        "review_status": "limited_slice_ship",
        "must1": "closed",
        "source_sha": "c691a0d5d0e06a4cc52567e1e816cd49cb0b1e7f",
        "source_tree": "9980da61338eb7b2b9202f98aa0c1055af1f9f70",
        "material_sha": "260942efc77168683b2b978747a19c3c9fedce3e",
        "material_tree": "b2444f8a03aadfef01e40a96eb79c2f60597b079",
        "report_raw_sha256": sha(REPORT.read_bytes()),
        "member_count": len(entries),
        "files": entries,
        "excluded": sorted(excluded),
        "distinct_tests": {"total": 299, "passed": 299, "failed": 0, "skipped": 0},
        "full_card_accepted": False,
        "overall_deadline_implemented": False,
        "runtime_secrets_obtained": 0,
        "product_or_paid_requests": 0,
    }
    manifest_path = RUN / "artifact_manifest.json"
    manifest_path.write_bytes(json.dumps(manifest, indent=2).encode() + b"\n")
    receipt = {
        "command": [sys.executable, str(Path(__file__).resolve())],
        "cwd": str(ROOT),
        "started_at": started,
        "finished_at": now(),
        "exit_code": 0,
        "report_path": str(REPORT),
        "report_raw_sha256": sha(REPORT.read_bytes()),
        "manifest_path": str(manifest_path),
        "manifest_raw_sha256": sha(manifest_path.read_bytes()),
        "member_count": len(entries),
        "status": "limited_slice_ship",
    }
    (RUN / "seal_receipt.json").write_bytes(json.dumps(receipt, indent=2).encode() + b"\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
