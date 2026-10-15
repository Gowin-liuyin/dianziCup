"""Collect immutable command metadata without counting repeated cases as new tests."""

from __future__ import annotations

import json
from pathlib import Path


run_root = Path(__file__).resolve().parent
commands = [json.loads(path.read_text(encoding="utf-8")) | {"run_name": path.name.removesuffix(".meta.json")} for path in run_root.glob("*.meta.json")]
commands.sort(key=lambda item: (item["started_at"], item["run_name"]))
(run_root / "commands.json").write_text(json.dumps(commands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
table = ["| run_id | Asia/Shanghai 开始 | 结束 | 退出码 | 命令 |", "|---|---|---|---:|---|"]
for command in commands:
    displayed_command = " ".join(command["command"]).replace("|", "\\|")
    table.append(f"| {command['run_name']} | {command['started_at']} | {command['ended_at']} | {command['exit_code']} | `{displayed_command}` |")
(run_root / "actual_commands.md").write_text("\n".join(table) + "\n", encoding="utf-8")
print(f"Recorded {len(commands)} actual command executions; every run has separate stdout/stderr and timestamps.")
