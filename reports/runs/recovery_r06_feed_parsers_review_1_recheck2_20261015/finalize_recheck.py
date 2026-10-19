"""Summarize the fixed review evidence and copy only owned deliverables with byte hashes."""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
ROOT = Path("D:/dianzi")
REPORT_RELATIVE = Path("reports/reviews/recovery/G-C-R06-feed-parsers-review-1-recheck2.md")
REPORT = WORKTREE / REPORT_RELATIVE
SHANGHAI = timezone(timedelta(hours=8))


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    fixture = (RUN / "test_independent_r06_feed_boundaries.py").read_bytes()
    assert digest(fixture) == "65b809db3152f99fdcc16dd7b2cff4fdbaaa050cc9ab57a21166c4425976e3fd"
    second_fixture = (RUN / "test_timezone_repair_boundary.py").read_bytes()
    assert (
        digest(second_fixture) == "4d2b198e5973eca99d7bb43f205750a2824469921558e1ac9d916c6d464d7244"
    )
    summary: dict[str, object] = {
        "original_47_sha256": digest(fixture),
        "original_2_sha256": digest(second_fixture),
    }
    for label, expected_total, expected_failed in (
        ("unit", 1135, 0),
        ("unit_contract_boundaries", 1203, 0),
    ):
        cases = list(ElementTree.parse(RUN / f"{label}.xml").getroot().iter("testcase"))
        counts = {
            "total": len(cases),
            "failed": sum(case.find("failure") is not None for case in cases),
            "error": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
        counts["passed"] = counts["total"] - counts["failed"] - counts["error"] - counts["skipped"]
        assert counts["total"] == expected_total
        assert counts["failed"] == expected_failed
        assert counts["error"] == counts["skipped"] == 0
        summary[label] = counts
        summary[f"{label}_coverage"] = json.loads((RUN / f"{label}_coverage.json").read_bytes())[
            "totals"
        ]
    traces = []
    for label in ("cbm_timezone_token", "cbm_published_at"):
        envelope = json.loads((RUN / f"{label}.log").read_bytes())
        assert envelope.get("isError") is False
        result = envelope["structuredContent"]
        assert "error" not in result and "ambiguous" not in result
        traces.append(
            {
                label: {
                    key: result.get(key)
                    for key in ("function", "direction", "callers_total", "callees_total")
                }
            }
        )
    summary["trace_summary"] = traces
    summary["generated_at"] = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", "backend/src", "backend/tests"],
        cwd=WORKTREE,
        check=True,
    )
    summary["tracked_src_tests_unchanged"] = True
    commands = []
    for path in RUN.glob("*.json"):
        record = json.loads(path.read_bytes())
        if isinstance(record, dict) and "command" in record and "started_at" in record:
            commands.append({"label": path.stem, **record})
    commands.sort(key=lambda record: (record["started_at"], record["label"]))
    summary["recorded_commands"] = len(commands)
    (RUN / "review_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (RUN / "command_ledger.json").write_text(
        json.dumps(commands, indent=2) + "\n", encoding="utf-8"
    )
    rows = [
        "\n## 实际命令账本\n",
        "每个标签链接到root副本的真实argv/cwd/ISO秒级+08:00/exit原件；同名log保留输出。\n",
        "| 标签 | cwd | 开始 / 结束 | exit | 命令 |",
        "|---|---|---|---:|---|",
    ]
    destination_run = ROOT / RUN.relative_to(WORKTREE)
    for record in commands:
        command = shlex.join(record["command"]).replace("|", "\\|")
        link = f"[{record['label']}]({destination_run.as_posix()}/{record['label']}.json)"
        rows.append(
            f"| {link} | `{record['cwd']}` | {record['started_at']} / "
            f"{record['completed_at']} | {record['exit_code']} | `{command}` |"
        )
    rows.append(f"\n写作结束/证据截止：{summary['generated_at']}。\n")
    marker = "<!-- GENERATED_COMMAND_LEDGER -->"
    REPORT.write_text(
        REPORT.read_text(encoding="utf-8").split(marker)[0] + marker + "\n" + "\n".join(rows),
        encoding="utf-8",
    )
    deliverables = [REPORT]
    deliverables.extend(
        path
        for path in RUN.iterdir()
        if path.is_file()
        and path.name != "artifact_copy_hashes.json"
        and (
            path.suffix in {".py", ".json", ".xml", ".log", ".txt", ".md"}
            or path.name == ".gitattributes"
        )
    )
    copied = []
    for source in sorted(deliverables):
        relative = source.relative_to(WORKTREE)
        destination = ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        source_payload = source.read_bytes()
        assert source_payload == destination.read_bytes()
        copied.append(
            {
                "path": relative.as_posix(),
                "bytes": len(source_payload),
                "sha256": digest(source_payload),
            }
        )
    receipt = {
        "generated_at": summary["generated_at"],
        "source_worktree": str(WORKTREE),
        "destination_root": str(ROOT),
        "copied_file_count": len(copied),
        "excluded": ["__pycache__", ".coverage.*", "artifact_copy_hashes.json (self)"],
        "files": copied,
    }
    payload = (json.dumps(receipt, indent=2) + "\n").encode()
    (RUN / "artifact_copy_hashes.json").write_bytes(payload)
    (destination_run / "artifact_copy_hashes.json").write_bytes(payload)
    assert (destination_run / "artifact_copy_hashes.json").read_bytes() == payload
    print(
        json.dumps(
            {
                "summary": summary,
                "copied_files": len(copied),
                "report_sha256": digest(REPORT.read_bytes()),
                "copy_receipt_sha256": digest(payload),
            }
        )
    )


if __name__ == "__main__":
    main()
