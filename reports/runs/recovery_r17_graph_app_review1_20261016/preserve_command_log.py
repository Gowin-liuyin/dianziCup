"""Retain original log bytes and carry valid records into the final log."""

import json
from pathlib import Path

run = Path(__file__).resolve().parent
path = run / "commands.jsonl"
raw = path.read_bytes()
(run / "commands.initial.raw.jsonl").write_bytes(raw)
valid = []
malformed = []
for index, line in enumerate(raw.decode("utf-8").splitlines()):
    try:
        valid.append(json.loads(line))
    except json.JSONDecodeError:
        malformed.append(index)
path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in valid), encoding="utf-8", newline="\n")
(run / "command-log-instrument-error.json").write_text(json.dumps({"cause": "Concurrent Windows append interleaved three initial CBM command records", "malformed_lines": malformed,
    "raw_preserved": "commands.initial.raw.jsonl", "valid_records_retained": len(valid),
    "followup": "Independently rerun schema, architecture, and Workbench trace sequentially with per-command receipt files; initial CBM stdout/stderr remain unchanged"}, indent=2) + "\n", encoding="utf-8", newline="\n")
