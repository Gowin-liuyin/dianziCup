"""Compare every new raw artifact with the staged blob before writing the manifest."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN_ROOT = Path(__file__).resolve().parent
WORKTREE = RUN_ROOT.parents[2]
CODE_SHA = "d8a3189bb7bc1cfde24825f5478920e37eac9556"
SOURCE_PATHS = (
    "backend/src/ai_intel/enrichment/model_fields.py",
    "backend/tests/unit/test_r07_single_model_dimension.py",
    "backend/tests/contract/test_r07_single_model_dimension_contract.py",
    "backend/tests/security/test_r07_single_model_dimension_security.py",
)


def git_bytes(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=WORKTREE)


def entry(path, reference):
    relative = path.relative_to(WORKTREE).as_posix()
    raw = path.read_bytes()
    blob_spec = f"{reference}:{relative}"
    blob = git_bytes("show", blob_spec)
    return {
        "path": relative,
        "raw_size_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "git_blob": git_bytes("rev-parse", blob_spec).decode().strip(),
        "git_blob_size_bytes": len(blob),
        "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
        "raw_equals_git_blob": raw == blob,
        "newline_normalized_equal": raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n"),
    }


source_entries = [entry(WORKTREE / path, CODE_SHA) for path in SOURCE_PATHS]
artifact_paths = [WORKTREE / ".gitattributes", WORKTREE / "reports/tasks/R07-single-model-dimension.md"]
artifact_paths += sorted(
    path for path in RUN_ROOT.iterdir()
    if path.is_file() and path.name not in ("material_manifest.json", "material_manifest.sha256")
)
artifacts = [entry(path, "") for path in artifact_paths]
assert all(record["raw_equals_git_blob"] for record in artifacts)
assert all(record["newline_normalized_equal"] for record in source_entries)
manifest = {
    "schema_version": 1,
    "recorded_at_shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
    "task_status": "awaiting_review",
    "code_sha": CODE_SHA,
    "baseline_sha": "cc1b1d302e22048f567475b7084bcd5490761ed2",
    "prerequisite_sha": "63e4cafe1363530eb08cdfe7fec56cfc07a81b8a",
    "sources": source_entries,
    "artifacts": artifacts,
    "artifact_count": len(artifacts),
    "exact_raw_blob_count": sum(record["raw_equals_git_blob"] for record in artifacts),
    "exclusions": ["material_manifest.json", "material_manifest.sha256"],
    "note": "Manifest and digest are excluded from their own recursive inventory; verify digest separately.",
}
output = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
(RUN_ROOT / "material_manifest.json").write_bytes(output)
digest = hashlib.sha256(output).hexdigest()
(RUN_ROOT / "material_manifest.sha256").write_text(digest + "\n", encoding="ascii", newline="\n")
print(json.dumps({"artifact_count": len(artifacts), "exact_raw_blob_count": manifest["exact_raw_blob_count"], "manifest_sha256": digest}))
