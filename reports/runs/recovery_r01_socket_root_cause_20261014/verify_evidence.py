"""Validate diagnostic receipts and save the exact source hashes without business-test claims."""

import ast
import hashlib
import json
from datetime import datetime
from pathlib import Path


directory = Path(__file__).resolve().parent
receipts = []
for path in directory.glob("*.json"):
    item = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(item, dict) and "probe_name" in item:
        assert item["timeout_seconds"] <= 30
        assert datetime.fromisoformat(item["started_at"]) <= datetime.fromisoformat(item["ended_at"])
        assert (directory / item["stdout_file"]).is_file()
        assert (directory / item["stderr_file"]).is_file()
        receipts.append(item)
source_hashes = {}
for path in directory.iterdir():
    if path.suffix in (".py", ".ps1", ".sh"):
        source = path.read_bytes()
        if path.suffix == ".py":
            ast.parse(source, filename=str(path))
        source_hashes[path.name] = hashlib.sha256(source).hexdigest()
assert not list(directory.glob("*.sock")), "Generated control sockets must be cleaned."
result = {"recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
          "business_unit_tests": "not_run", "diagnostic_receipts": len(receipts),
          "source_sha256": source_hashes,
          "commands": sorted(receipts, key=lambda item: item["started_at"])}
(directory / "commands.json").write_text(json.dumps(result, indent=2))
print(json.dumps({"receipts_validated": len(receipts), "sources_parsed_or_hashed": len(source_hashes),
                  "business_unit_tests": "not_run", "generated_control_sockets_remaining": 0}, indent=2))
