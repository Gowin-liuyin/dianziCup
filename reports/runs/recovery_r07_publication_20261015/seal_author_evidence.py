"""Preserve fixed-candidate author logs without claiming independent acceptance."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SHA = "71e594cb958bd93d21fb7ed66574b3cba4cc47e1"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


assert git("rev-parse", "HEAD") == SHA
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests")
manifest_path = RUN / "artifact_manifest.json"
assert not manifest_path.exists()
report_path = ROOT / "reports/tasks/R07-enrichment-publication.md"
members = [report_path] + sorted(path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
entries = [{"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in members]
source_paths = git("diff", "--name-only", "23f5186^", SHA, "--", "backend/src", "backend/tests", "docs/decisions/CR-R07_multisource_enrichment_publication.md").splitlines()
source_entries = []
for path in source_paths:
    raw = subprocess.check_output(["git", "show", SHA + ":" + path], cwd=ROOT)
    source_entries.append({"path": path, "git_blob_sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
manifest = {"schema_version": "recovery-r07-publication-author-evidence-1", "sealed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": SHA, "task_status": "awaiting_review", "known_independent_musts": ["parent_source_document_acl", "source_publication_lock_order", "cvss_authority_scope"], "scope": "fixed service candidate only; no worker/model/source live or stage gate", "files": entries, "code_files": source_entries, "raw_transcoding": "none; original errors and failed tests retained"}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
sidecar = RUN / "artifact_manifest.sha256"
sidecar.write_text(digest + "  artifact_manifest.json\n", encoding="utf-8")
attributes_path = ROOT / ".gitattributes"
attributes = attributes_path.read_text(encoding="utf-8")
for line in (
    "reports/runs/recovery_r07_publication_20261015/** -text whitespace=trailing-space,space-before-tab,cr-at-eol",
    "reports/runs/recovery_r07_publication_20261015/*.log -diff",
    "reports/runs/recovery_r07_publication_20261015/*.xml -diff",
    "reports/tasks/R07-enrichment-publication.md -text",
):
    if line not in attributes.splitlines():
        attributes += ("" if attributes.endswith("\n") else "\n") + line + "\n"
attributes_path.write_text(attributes, encoding="utf-8")
paths = [entry["path"] for entry in entries] + [manifest_path.relative_to(ROOT).as_posix(), sidecar.relative_to(ROOT).as_posix(), ".gitattributes"]
subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True)
assert set(git("diff", "--cached", "--name-only").splitlines()) == set(paths)
for entry in entries + [{"path": manifest_path.relative_to(ROOT).as_posix(), "sha256": digest}]:
    blob = subprocess.check_output(["git", "show", ":" + entry["path"]], cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest() == entry["sha256"], entry["path"]
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "G-C R07 freeze author publication evidence with unresolved independent findings"], cwd=ROOT, check=True, capture_output=True)
print(json.dumps({"code_sha": SHA, "material_sha": git("rev-parse", "HEAD"), "manifest_sha256": digest, "member_count": len(entries), "raw_blob_mismatches": 0, "accepted": False}))
