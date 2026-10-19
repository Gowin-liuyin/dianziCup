"""Inspect only the authorized run's exported objects, reporting hashes and format signatures."""

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

from ai_intel.ingestion.catalog_pages import select_avid_blob
from ai_intel.ingestion.cursor_repository import _cursor_state

from replay_originals import RUN, current_time

started_at = current_time()
directory = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/originals")
counts = Counter()
possible_atom = []
hash_errors = []
for path in directory.glob("*.body"):
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if digest != path.stem:
        hash_errors.append(path.name)
    prefix = body[:2048].lstrip()
    if prefix.startswith(b"%PDF"):
        signature = "pdf"
    elif prefix.startswith((b"{", b"[")):
        signature = "json"
    elif b"<feed" in prefix and b"http://www.w3.org/2005/Atom" in prefix:
        signature = "possible_arxiv_atom"
        possible_atom.append({"sha256": digest, "size_bytes": len(body), "path": str(path)})
    elif b"<rss" in prefix:
        signature = "rss_xml"
    elif b"<html" in prefix.lower() or b"<!doctype html" in prefix.lower():
        signature = "html"
    else:
        signature = "unclassified"
    counts[signature] += 1

receipt = json.loads(Path("D:/dianzi/reports/runs/recovery_r06_integrated_live_20261015/collection_receipt.json").read_text(encoding="utf-8"))
avid_id = "959a51b7-3134-5d93-8506-9e3b3dae8a64"
pg_cursor = next(row["cursor_json"] for row in receipt["cursors"] if row["source_id"] == avid_id)
actual_position = _cursor_state(pg_cursor)[0]
tree_path = directory / "0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5.body"
selected = select_avid_blob(tree_path.read_bytes(), actual_position)
output = {"source_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215", "argv": sys.argv,
          "cwd": os.getcwd(), "started_at": started_at, "finished_at": current_time(),
          "directory": str(directory), "objects_scanned": sum(counts.values()),
          "signature_counts": dict(counts), "hash_errors": hash_errors,
          "possible_arxiv_atom": possible_atom, "actual_avid_position": actual_position,
          "second_avid_selection": {"tree_sha": selected.tree_sha, "blob_sha": selected.blob_sha,
                                    "path": selected.path, "next_cursor": selected.next_cursor},
          "network_requests": 0, "database_calls": 0, "exit_code": 0}
(RUN / "saved_object_signatures.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(json.dumps(output, indent=2))
