"""Independently compare every frozen raw artifact and source blob to actual bytes."""

import hashlib
import json
import subprocess
from pathlib import Path

from review_runner import ROOT, RUN, now

AUTHOR = ROOT / "reports/runs/recovery_r11_pg_assessments_20261016"
CODE = "d56a1ed306d975be408a2f6f8fbe3e905d940643"
MATERIAL = "ad122224b02ec16194e03f937b02a218ff6faaa5"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


entries = json.loads((AUTHOR / "artifact_manifest.json").read_text())
seen = {entry["path"] for entry in entries}
discovered = {str(path.relative_to(ROOT)).replace("\\", "/") for path in AUTHOR.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name != "artifact_manifest.json"}
raw_proofs = []
for entry in entries:
    path = ROOT / entry["path"]
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    raw_proofs.append(dict(path=entry["path"], expected_bytes=entry["bytes"], expected_sha256=entry["sha256"], actual_bytes=len(raw), actual_sha256=sha(raw), lf_sha256=sha(lf), crlf_pairs=raw.count(b"\r\n"), exact_raw_match=len(raw) == entry["bytes"] and sha(raw) == entry["sha256"]))
source_proofs = []
for entry in json.loads((AUTHOR / "source_manifest.json").read_text()):
    raw = (ROOT / entry["path"]).read_bytes()
    blob = git("show", CODE + ":" + entry["path"])
    actual_blob_id = git("rev-parse", CODE + ":" + entry["path"]).decode().strip()
    raw_match = sha(raw) == entry["sha256"]
    lf_match = sha(raw.replace(b"\r\n", b"\n")) == entry["sha256"]
    source_proofs.append(dict(path=entry["path"], raw_bytes=len(raw), actual_raw_sha256=sha(raw), lf_sha256=sha(raw.replace(b"\r\n", b"\n")), expected_raw_sha256=entry["sha256"], expected_blob_id=entry["git_blob"], actual_blob_id=actual_blob_id, expected_blob_sha256=entry["git_blob_sha256"], actual_blob_sha256=sha(blob), raw_match=raw_match, lf_match=lf_match, portable_content_match=raw_match or lf_match, blob_match=actual_blob_id == entry["git_blob"] and sha(blob) == entry["git_blob_sha256"]))
proof = dict(checked_at=now(), code_sha=CODE, material_sha=MATERIAL, worktree_head=git("rev-parse", "HEAD").decode().strip(), manifest_actual_sha256=sha((AUTHOR / "artifact_manifest.json").read_bytes()), manifest_actual_bytes=(AUTHOR / "artifact_manifest.json").stat().st_size, declared_raw_count=len(entries), discovered_raw_count=len(discovered), missing=sorted(seen-discovered), undeclared=sorted(discovered-seen), raw_mismatch_count=sum(not row["exact_raw_match"] for row in raw_proofs), raw_proofs=raw_proofs, source_count=len(source_proofs), source_raw_mismatch_count=sum(not row["raw_match"] for row in source_proofs), source_mismatch_count=sum(not (row["portable_content_match"] and row["blob_match"]) for row in source_proofs), source_proofs=source_proofs, author_report=dict(path="reports/tasks/R11-pg-rules-assessments.md", expected_sha256=None, actual_sha256=sha((ROOT / "reports/tasks/R11-pg-rules-assessments.md").read_bytes())), production_0021_files=[str(p.relative_to(ROOT)) for p in (ROOT / "backend/migrations/versions").glob("0021*")])
if (RUN / "author_raw_and_source_proof.json").exists() and not (RUN / "author_raw_and_source_proof_initial_crlf.json").exists():
    (RUN / "author_raw_and_source_proof_initial_crlf.json").write_bytes((RUN / "author_raw_and_source_proof.json").read_bytes())
(RUN / "author_raw_and_source_proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
(RUN / "author_artifact_manifest.exact.json").write_bytes((AUTHOR / "artifact_manifest.json").read_bytes())
(RUN / "author_source_manifest.exact.json").write_bytes((AUTHOR / "source_manifest.json").read_bytes())
assert not proof["missing"] and not proof["undeclared"] and proof["raw_mismatch_count"] == proof["source_mismatch_count"] == 0
print(json.dumps({key: proof[key] for key in ("declared_raw_count", "discovered_raw_count", "raw_mismatch_count", "source_count", "source_mismatch_count", "manifest_actual_sha256")}))
