"""Archive the full cross-platform Git diagnostic without discarding the original log."""

import gzip
import hashlib
import json
from pathlib import Path

directory = Path(__file__).resolve().parent
source = directory / "diff.log"
raw = source.read_bytes()
archive = directory / "diff.log.gz"
with gzip.GzipFile(filename=str(archive), mode="wb", mtime=0) as stream:
    stream.write(raw)
assert gzip.decompress(archive.read_bytes()) == raw
record = {
    "source": source.name,
    "archive": archive.name,
    "original_bytes": len(raw),
    "original_sha256": hashlib.sha256(raw).hexdigest(),
    "archive_bytes": archive.stat().st_size,
    "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "lossless_roundtrip": True,
    "original_preserved_in_worktree": True,
}
(directory / "large_diagnostic_archive.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record))
