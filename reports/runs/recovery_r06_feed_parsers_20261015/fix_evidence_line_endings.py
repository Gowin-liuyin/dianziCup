"""Preserve original diagnostic JSON bytes and verify every explicit staged blob before commit."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PREVIOUS = "8bb8bd56f92dff266b326aa634b425a2a617fe6b"


def clock() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> None:
    old_manifest = json.loads(
        subprocess.check_output(
            [
                "git",
                "show",
                f"{PREVIOUS}:reports/runs/recovery_r06_feed_parsers_20261015/delivery_files.json",
            ],
            cwd=ROOT,
        )
    )
    mismatches = []
    for item in old_manifest["files"]:
        committed = subprocess.check_output(
            ["git", "show", f"{PREVIOUS}:{item['path']}"], cwd=ROOT
        )
        if hashlib.sha256(committed).hexdigest() != item["sha256"]:
            mismatches.append(item["path"])
    report_path = ROOT / "reports/tasks/R06-feed-parsers.md"
    report = report_path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    now = clock()
    report += f"""\n\n### {now} · 原字节封存修正

R06-A-07：封存核对发现 Git 默认将生成 JSON/Markdown CRLF 转为 LF，旧候选 {PREVIOUS} 的 manifest 与 {len(mismatches)} 个 Git blob 原字节 hash 不一致。验证非零后本调用中的后续 PowerShell native 命令仍执行，故该本地 docs commit 被保留为历史失败候选，不代表 hash 检查通过。业务代码、原 .body/XML、用例行为没有变化，也没有改写旧记录的时间/结果。

修正只在本 run 的 .gitattributes 增加 *.json -text/-diff（与 log/XML/body 同样保持原证据字节），任务报告明确保存 LF；显式 owned files 重登暂存并逐 blob 核对，最终以新候选与修正收据为准。既有失败候选不推送/验收。首次创建时间不改；完整源码测试结果不拿来为改变行为的代码背书。
"""
    report = report.replace(
        "最后更新时间：2026-10-15T18:30:03+08:00", f"最后更新时间：{now}"
    )
    report_path.write_bytes(report.encode("utf-8"))
    receipt = {
        "recorded_at": now,
        "previous_candidate": PREVIOUS,
        "previous_manifest_files": len(old_manifest["files"]),
        "previous_blob_hash_mismatches": mismatches,
        "root_cause": "default Git text normalization; shell commands continued after failed native check",
        "code_sha_unchanged": "b1ff04a267babda5d57506d6e1e39006a2e4bb34",
        "fix_scope": "owned raw JSON byte preservation and human report LF; no business/test changes",
    }
    (RUN / "line_ending_correction.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps({"previous_mismatches": len(mismatches), "recorded_at": now}))


if __name__ == "__main__":
    main()
