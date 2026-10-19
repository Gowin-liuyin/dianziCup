"""Inspect a shared command log without suppressing malformed raw records."""

import json
from pathlib import Path

run = Path(__file__).resolve().parent
for index, line in enumerate((run / "commands.jsonl").read_text(encoding="utf-8").splitlines()):
    try:
        print(index, json.loads(line)["label"])
    except json.JSONDecodeError:
        print(index, repr(line))
