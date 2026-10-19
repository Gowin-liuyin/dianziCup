"""Keep original CRLF input bytes recoverable without changing repository attributes."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

RUN = Path(__file__).resolve().parent
path = RUN / "frozen_inputs.json"
inputs = json.loads(path.read_text(encoding="utf-8"))
with ZipFile(RUN / "frozen_inputs_raw.zip", "w", compression=ZIP_DEFLATED) as archive:
    for item in inputs:
        raw = (RUN / item["snapshot"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["sha256_raw"]
        entry = ZipInfo(item["snapshot"], date_time=(2026, 10, 16, 0, 0, 0))
        entry.compress_type = ZIP_DEFLATED
        archive.writestr(entry, raw)
        item["sha256_git_lf"] = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        item["raw_archive"] = "frozen_inputs_raw.zip"
        item["raw_archive_entry"] = item["snapshot"]
path.write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"input_bytes_archived": len(inputs), "attributes_changed": False}))
