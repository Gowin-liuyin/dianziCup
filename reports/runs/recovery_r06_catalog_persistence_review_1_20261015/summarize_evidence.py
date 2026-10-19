"""Build review summaries from raw command ledger and JUnit, without inventing results."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

RUN = Path(__file__).resolve().parent
commands = [json.loads(line) for line in (RUN / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
lines = ["# Actual review command ledger", "", "Times are ISO +08:00; argv is literal, with no credentials.", "",
         "| Label / SHA | Started → ended | Exit | cwd / argv |", "|---|---|---:|---|"]
for command in commands:
    arguments = json.dumps(command["argv"], ensure_ascii=False).replace("|", "\\|")
    lines.append(f'| {command["label"]} / `{command["sha"]}` | {command["started_at"]} → {command["ended_at"]} | {command["exit_code"]} | `{command["cwd"]}`<br>`{arguments}` |')
(RUN / "command_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
summaries = []
for path in sorted(RUN.glob("*.xml")):
    root = ET.parse(path).getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    summaries.append({"path": path.name, **{key: suite.get(key) for key in ("tests", "errors", "failures", "skipped", "time", "timestamp")}})
(RUN / "junit_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for command in commands:
    for stream in ("stdout", "stderr"):
        observed = hashlib.sha256((RUN / command[stream]).read_bytes()).hexdigest()
        assert observed == command[stream + "_sha256"], command["label"]
print(json.dumps({"commands": len(commands), "raw_log_hashes_verified": len(commands) * 2,
                  "junit_files": len(summaries)}))
