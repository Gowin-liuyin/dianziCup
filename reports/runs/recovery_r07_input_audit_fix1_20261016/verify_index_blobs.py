"""Verify staged raw bytes separately from normalized committed business source."""

import hashlib
import io
import json
import subprocess
from pathlib import Path
from checks import ROOT, RUN, now

started = now()
manifest = json.loads((RUN / "raw_manifest.json").read_bytes())
paths = [ROOT / item["path"] for item in manifest["materials"]]
paths += [RUN / "raw_manifest.json", RUN / "material_fingerprint.json"]
references = [":" + path.relative_to(ROOT).as_posix() for path in paths]
source = manifest["changed_source"]
references += [manifest["code_sha"] + ":" + item["path"] for item in source]
stream = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], cwd=ROOT, input="".join(reference + "\n" for reference in references).encode()))
rows = []
for index, reference in enumerate(references):
    header = stream.readline().decode().split()
    assert len(header) == 3 and header[1] == "blob"
    raw = stream.read(int(header[2]))
    assert stream.read(1) == b"\n"
    digest = hashlib.sha256(raw).hexdigest()
    if index < len(paths):
        expected = hashlib.sha256(paths[index].read_bytes()).hexdigest()
    else:
        expected = source[index - len(paths)]["code_git_blob_sha256"]
    assert digest == expected, reference
    rows.append({"reference": reference, "git_blob_sha256": digest, "expected_sha256": expected, "match": True})
receipt = {"started_at": started, "ended_at": now(), "exit_code": 0, "code_sha": manifest["code_sha"], "raw_manifest_sha256": hashlib.sha256((RUN / "raw_manifest.json").read_bytes()).hexdigest(), "raw_material_git_blobs_verified": len(paths), "source_git_blobs_verified": len(source), "all_raw_hashes_match": True, "rows": rows, "self_record": "not part of raw manifest; independently checked after material commit", "cache_policy": "excluded; no cache content read"}
(RUN / "index_blob_verification.json").write_bytes(json.dumps(receipt, indent=2).encode())
print(json.dumps({"raw_material_git_blobs_verified": len(paths), "source_git_blobs_verified": len(source), "all_raw_hashes_match": True}))
