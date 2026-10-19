"""Verify frozen author manifests and byte identity against the reviewed combination."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAW = Path(__file__).resolve().parent
ROOT = RAW.parents[2]
AUTHORS = (
    ("acl_lock", Path("D:/wt/r07-pub-fix"), "b0a5b64014f89a689b6b1efcdd21e791b454c12f", "reports/runs/recovery_r07_publication_acl_lock_fix_20261016/raw_manifest.json"),
    ("cvss", Path("D:/wt/r07-cvss-scope"), "fde252955fd88f537b844b0414d08967d0b2d67a", "reports/runs/recovery_r07_cvss_authority_scope_fix_20261016/artifact_manifest.json"),
)


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout


checks = []
for label, author_root, material_sha, relative in AUTHORS:
    manifest_path = author_root / relative
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = data["artifacts"]
    rows = [{"path": name, **metadata} for name, metadata in artifacts.items()] if isinstance(artifacts, dict) else artifacts
    mismatches = []
    for row in rows:
        name = row["path"]
        candidate = manifest_path.parent / name if label == "acl_lock" else author_root / name
        if not candidate.exists():
            candidate = author_root / name
        if not candidate.exists() or hashlib.sha256(candidate.read_bytes()).hexdigest() != row["sha256"]:
            mismatches.append(name)
    record = {"label": label, "material_sha": material_sha, "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "artifact_count": len(rows), "mismatches": mismatches,
        "manifest_in_frozen_material": hashlib.sha256(git(author_root, "show", material_sha + ":" + relative)).hexdigest() == hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    checks.append(record)

code_comparisons = []
for label, author_root, material_sha, relative in AUTHORS:
    paths = ["backend/src/ai_intel/enrichment/inputs.py", "backend/tests/integration/test_r07_publication_acl_lock_fix_pg.py"] if label == "acl_lock" else [
        "backend/src/ai_intel/enrichment/signals.py", "backend/tests/unit/test_r07_public_signals.py", "backend/tests/unit/test_r07_public_signals_fix1.py",
        "backend/tests/unit/test_r07_cvss_authority_scope_fix.py", "backend/tests/contract/test_r07_cvss_authority_scope_contract.py", "backend/tests/integration/test_r07_cvss_authority_scope_fix_pg.py"]
    for path in paths:
        frozen = git(author_root, "show", material_sha + ":" + path)
        reviewed = git(ROOT, "show", "HEAD:" + path)
        code_comparisons.append({"label": label, "path": path, "same_blob_bytes": frozen == reviewed,
            "author_sha256": hashlib.sha256(frozen).hexdigest(), "reviewed_sha256": hashlib.sha256(reviewed).hexdigest()})

shared = []
for path in ("backend/src/ai_intel/ingestion/source_documents.py", "backend/src/ai_intel/ingestion/catalog_documents.py", "backend/src/ai_intel/knowledge/revisions.py", "backend/src/ai_intel/knowledge/event_linking.py", "backend/src/ai_intel/knowledge/persistence.py", "backend/src/ai_intel/api/knowledge_read_service.py"):
    baseline = git(ROOT, "show", "71e594cb958bd93d21fb7ed66574b3cba4cc47e1:" + path)
    current = git(ROOT, "show", "HEAD:" + path)
    shared.append({"path": path, "same_blob_bytes": baseline == current, "sha256": hashlib.sha256(current).hexdigest()})
publication_delta = git(ROOT, "diff", "a80408fb35addf35c04a91d255f20fb9a987423e..HEAD", "--", "backend/src/ai_intel/enrichment/publication.py").decode()
(RAW / "root_provenance_delta.diff").write_text(publication_delta, encoding="utf-8")
record = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "authors": checks,
    "author_code_comparisons": code_comparisons, "unchanged_shared": shared,
    "old_probe_sha256": hashlib.sha256((RAW / "test_original_probe_unchanged.py").read_bytes()).hexdigest()}
(RAW / "author_material_audit.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"authors": checks, "code_comparisons_pass": all(row["same_blob_bytes"] for row in code_comparisons),
    "shared_unchanged": all(row["same_blob_bytes"] for row in shared), "old_probe_sha256": record["old_probe_sha256"]}, ensure_ascii=False))
