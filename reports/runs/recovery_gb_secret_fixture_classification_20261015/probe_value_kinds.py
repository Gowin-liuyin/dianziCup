"""Report source and marker properties without exposing matched values."""

import hashlib
import json
import re
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
metadata_path = RUN / "unclassified_metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
for item in metadata["occurrences"]:
    item.pop("redacted_context", None)
    if "/venv/" in item["path"]:
        continue
    raw = (ROOT / item["path"]).read_bytes()
    content = raw.decode("utf-8",errors="ignore").replace("\r\n","\n").replace("\r","\n")
    span = content[item["start"]:item["end"]]
    quote_start = min(index for index, character in enumerate(span) if character in "\"'")
    value = span[quote_start+1:-1]
    print(json.dumps({"path":item["path"],"line":item["line"],"length":len(value),"has_fixture_marker":"fixture" in value.lower(),"has_synthetic_marker":"synthetic" in value.lower(),"has_redaction_marker":any(marker in value.lower() for marker in ("redact", "sanitiz")),"public_pg_failure_text":value == "password authentication failed","source_unchanged":hashlib.sha256(raw).hexdigest() == item["raw_sha256"]},ensure_ascii=False))
metadata_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
