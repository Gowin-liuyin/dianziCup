"""Freeze review evidence and source blobs; verify hashes immediately after writing."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md"
PATHS = (
    "backend/src/ai_intel/enrichment/evidence_selection.py",
    "backend/src/ai_intel/enrichment/model_fields.py",
    "backend/src/ai_intel/enrichment/taxonomy_inputs.py",
    "backend/src/ai_intel/enrichment/field_sources.py",
    "backend/tests/contract/test_r07_input_selection_codec.py",
    "backend/tests/integration/test_r07_input_capabilities_pg.py",
    "backend/tests/security/test_r07_input_capabilities_boundary.py",
    "backend/tests/unit/test_r07_input_capabilities.py",
    "docs/decisions/CR-R07_bounded_evidence_and_taxonomy_inputs.md",
    "docs/decisions/CR-R07_context_validation_seam.md",
    "docs/decisions/CR-R07_fix3_scalar_constructor_boundary.md",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    source_sha, material_sha = sys.argv[1:3]
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    source_records = []
    for revision in dict.fromkeys(("7dae1d82363d8459f3546fee4b92137559dcb5aa", "9c4991a218e3d7208d8c314a3992cd6c499e0b4b", "7aeb85ae8277c048fb762dbc705436602cb18f9d", source_sha)):
        for relative in PATHS:
            exists = subprocess.run(["git", "cat-file", "-e", revision + ":" + relative], cwd=ROOT, capture_output=True)
            if exists.returncode:
                continue
            blob = subprocess.check_output(["git", "show", revision + ":" + relative], cwd=ROOT)
            path = RUN / "source_blobs" / revision / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
            assert path.read_bytes() == blob
            source_records.append({"source_commit": revision, "source_path": relative, "saved_path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(blob), "git_blob_sha256": sha(blob)})
    for relative in PATHS:
        blob = subprocess.check_output(["git", "show", source_sha + ":" + relative], cwd=ROOT)
        current = (ROOT / relative).read_bytes()
        assert current.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
    files = []
    excluded = {"review_manifest.json", "review_manifest_fingerprint.json", "review_seal_receipt.json"}
    for path in sorted([REPORT, *RUN.rglob("*")]):
        if not path.is_file() or path.name in excluded or "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        files.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(raw), "raw_sha256": sha(raw), "lf_normalized_sha256": sha(raw.replace(b"\r\n", b"\n"))})
    result = {"created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "author_source_sha": source_sha, "author_material_sha": material_sha, "review_tree_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "report_sha256": sha(REPORT.read_bytes()), "source_blobs": source_records, "files": files}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    (RUN / "review_manifest.json").write_bytes(encoded)
    fingerprint = {"manifest_raw_sha256": sha(encoded), "files": len(files), "source_blobs": len(source_records), "author_source_sha": source_sha, "author_material_sha": material_sha}
    (RUN / "review_manifest_fingerprint.json").write_bytes((json.dumps(fingerprint, indent=2) + "\n").encode())
    for item in files:
        raw = (ROOT / item["path"]).read_bytes()
        assert sha(raw) == item["raw_sha256"] and len(raw) == item["bytes"]
    assert sha((RUN / "review_manifest.json").read_bytes()) == fingerprint["manifest_raw_sha256"]
    receipt = {"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "command": [sys.executable, str(Path(__file__).resolve()), source_sha, material_sha], "cwd": str(ROOT), "exit_code": 0, "all_hashes_and_lengths_verified": True, **fingerprint}
    (RUN / "review_seal_receipt.json").write_bytes((json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
