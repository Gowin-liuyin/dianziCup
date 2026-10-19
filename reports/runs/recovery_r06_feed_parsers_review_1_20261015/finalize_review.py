"""Summarize existing independent evidence and append its recorded command ledger."""

from __future__ import annotations

import ast
import hashlib
import json
import shlex
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
REPORT = Path("D:/dianzi/reports/reviews/recovery/G-C-R06-feed-parsers-review-1.md")
SHANGHAI = timezone(timedelta(hours=8))


def function_tree(payload: str, names: set[str]) -> dict[str, str]:
    module = ast.parse(payload)
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }


def main() -> None:
    original = (RUN / "tested_independent_47.py.txt").read_bytes()
    formatted = (RUN / "test_independent_r06_feed_boundaries.py").read_bytes()
    names = {
        "atom",
        "entry",
        "rss",
        "item",
        "test_atom_underfull_nonfinal_page_is_not_success",
        "test_rss_invalid_numeric_timezone_minutes_are_rejected",
        "test_rss_del_control_character_uri_is_rejected",
        "test_arxiv_del_control_character_license_is_rejected",
    }
    assert function_tree(original.decode(), names) == function_tree(formatted.decode(), names)
    summary: dict[str, object] = {
        "original_47_sha256": hashlib.sha256(original).hexdigest(),
        "formatted_47_sha256": hashlib.sha256(formatted).hexdigest(),
        "four_red_cases_and_builders_ast_equal": True,
    }
    for label in ("unit", "unit_contract_independent"):
        root = ElementTree.parse(RUN / f"{label}.xml").getroot()
        cases = list(root.iter("testcase"))
        counts = {
            "total": len(cases),
            "failed": sum(case.find("failure") is not None for case in cases),
            "error": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
        counts["passed"] = counts["total"] - counts["failed"] - counts["error"] - counts["skipped"]
        summary[label] = counts
    assert summary["unit"] == {"total": 1086, "failed": 0, "error": 0, "skipped": 0, "passed": 1086}
    assert summary["unit_contract_independent"] == {
        "total": 1147,
        "failed": 4,
        "error": 0,
        "skipped": 0,
        "passed": 1143,
    }
    for label in ("unit", "unit_contract_independent"):
        coverage = json.loads((RUN / f"{label}_coverage.json").read_bytes())
        summary[f"{label}_coverage_totals"] = coverage["totals"]
    commands = []
    for path in sorted(RUN.glob("*.json")):
        value = json.loads(path.read_bytes())
        if isinstance(value, dict) and "command" in value and "started_at" in value:
            commands.append({"label": path.stem, **value})
    commands.sort(key=lambda value: (value["started_at"], value["label"]))
    generated = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    summary["generated_at"] = generated
    summary["recorded_commands"] = len(commands)
    (RUN / "review_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (RUN / "command_ledger.json").write_text(
        json.dumps(commands, indent=2) + "\n", encoding="utf-8"
    )
    rows = [
        "\n## 实际命令账本\n",
        "每行链接指向参数原件JSON；同名.log保留原输出。所有时间均+08:00。\n",
        "| 标签 | cwd | 开始 / 结束 | exit | 原命令 |",
        "|---|---|---|---:|---|",
    ]
    for record in commands:
        command = shlex.join(record["command"]).replace("|", "\\|")
        link = f"[{record['label']}]({RUN.as_posix()}/{record['label']}.json)"
        rows.append(
            f"| {link} | `{record['cwd']}` | {record['started_at']} / "
            f"{record['completed_at']} | {record['exit_code']} | `{command}` |"
        )
    rows.append(f"\n写作结束/证据截止：{generated}。生成收据：`review_summary.json`。\n")
    marker = "<!-- GENERATED_COMMAND_LEDGER -->"
    report = REPORT.read_text(encoding="utf-8").split(marker)[0]
    REPORT.write_text(report + marker + "\n" + "\n".join(rows), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
