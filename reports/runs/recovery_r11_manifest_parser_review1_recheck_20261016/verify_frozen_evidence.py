"""Verify fixed evidence and stream old raw logs without reading or printing payload lines."""

import gzip
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "e651a0576785de4d8f9bf4e0dd114c8984bfd2d3"
CODE = "64dcd946601cd0e0f7435f59019ee709e3738a35"
FIXED = "37e492b4e26fc5b6197b60d2494926d4181a21c3"
AUTHOR_RUN = "reports/runs/recovery_r11_manifest_parser_fix1_20261016"
OLD_RUN = "reports/runs/recovery_r11_manifest_parser_20261016"
INITIAL_ROOT = Path("D:/wt/r11-review1")
INITIAL_RUN = "reports/runs/recovery_r11_manifest_parser_review1_20261016"


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def blob(revision: str, path: str) -> bytes:
    return git("show", f"{revision}:{path}")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def stream_hash(stream) -> tuple[int, str]:
    count = 0
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        count += len(chunk)
        digest.update(chunk)
    return count, digest.hexdigest()


def verify_entries(manifest, revision: str):
    records = []
    for item in manifest["artifacts"]:
        value = blob(revision, item["path"])
        records.append({"path": item["path"], "size_bytes": len(value), "sha256": sha(value), "matches": len(value) == item["size_bytes"] and sha(value) == item["sha256"]})
    return records


def main() -> None:
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    new_body = blob(FIXED, f"{AUTHOR_RUN}/artifact_manifest.json")
    new_manifest = json.loads(new_body)
    new_records = verify_entries(new_manifest, FIXED)
    source = []
    for item in new_manifest["source_proof"]:
        value = blob(CODE, item["path"])
        source.append({"path": item["path"], "sha256": sha(value), "code_material_equal": value == blob(FIXED, item["path"]), "working_git_object_equal": git("hash-object", item["path"]).strip() == git("rev-parse", f"{FIXED}:{item['path']}").strip(), "matches": len(value) == item["size_bytes"] and sha(value) == item["sha256"] and value == blob(FIXED, item["path"])})
    old_body = blob(BASE, f"{OLD_RUN}/evidence_manifest.json")
    old_manifest = json.loads(old_body)
    old_records = verify_entries(old_manifest, BASE)
    allowed_changes = {".gitattributes", "backend/src/ai_intel/assets/manifest_parser.py"}
    preserved = [{"path": item["path"], "matches": blob(BASE, item["path"]) == blob(FIXED, item["path"])} for item in old_manifest["artifacts"] if item["path"] not in allowed_changes]
    old_manifest_preserved = old_body == blob(FIXED, f"{OLD_RUN}/evidence_manifest.json")
    initial_body = (INITIAL_ROOT / INITIAL_RUN / "artifact_manifest.json").read_bytes()
    initial_manifest = json.loads(initial_body)
    initial_records = []
    for item in initial_manifest["files"]:
        value = (INITIAL_ROOT / item["path"]).read_bytes()
        initial_records.append({"path": item["path"], "matches": len(value) == item["size_bytes"] and sha(value) == item["sha256"]})
    original_probe = (INITIAL_ROOT / INITIAL_RUN / "test_independent_manifest_review.py").read_bytes()
    probe = blob(FIXED, f"{AUTHOR_RUN}/test_independent_manifest_review.py")
    probe_matches = original_probe == probe == (ROOT / AUTHOR_RUN / "test_independent_manifest_review.py").read_bytes()
    compressed = ROOT / OLD_RUN / "green_boundary.stdout.log.gz"
    with gzip.open(compressed, "rb") as stream:
        decompressed_size, decompressed_sha = stream_hash(stream)
    external = Path("D:/dianzi-local-evidence/recovery_r11_manifest_parser_20261016/green_boundary.stdout.log")
    with external.open("rb") as stream:
        external_size, external_sha = stream_hash(stream)
    raw_matches = compressed.stat().st_size == 44590 and sha(compressed.read_bytes()) == "6a03747311af06c0812c21743004c3cc046ac1a2f62dd9b60f004e0ce759cad6" and decompressed_size == external_size == 41951937 and decompressed_sha == external_sha == "3cccbce776d43c2fb1910a851859ae70de0d3290a387efbd870814e78d8b0323"
    receipt = {
        "started_at": started, "ended_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "code_sha": CODE, "material_sha": FIXED,
        "new_manifest_body_sha256": sha(new_body), "new_manifest_matches": sha(new_body) == "c0cb74e7019bf4588e76143d3b019f9ac0c3aa35fc36397f964808bd64689a68",
        "new_artifacts": new_records, "new_source": source,
        "old_manifest_body_sha256": sha(old_body), "old_manifest_matches": sha(old_body) == "e1827675743d736036c0d6ded14ce3243280ef96dd694033a431253066d30a92" and old_manifest_preserved,
        "old_artifacts_baseline": old_records, "old_current_preserved": preserved,
        "allowed_changed_old_paths": sorted(allowed_changes),
        "initial_manifest_body_sha256": sha(initial_body), "initial_manifest_matches": sha(initial_body) == "1c644e365aaf9bf1d5ad9a273f0c85da669f3609162b51cad6cbfc980051c0e0",
        "initial_review_files": initial_records,
        "original_38_probe_sha256": sha(probe), "original_38_probe_matches": probe_matches and sha(probe) == "ac13a06334ea163e5c3f95da0d7592aaa7c61a232b1ed7178be6b99983ab2b1c",
        "raw_failure": {"compressed_size": compressed.stat().st_size, "compressed_sha256": sha(compressed.read_bytes()), "decompressed_size": decompressed_size, "decompressed_sha256": decompressed_sha, "external_size": external_size, "external_sha256": external_sha, "matches": raw_matches},
    }
    passed = receipt["new_manifest_matches"] and receipt["old_manifest_matches"] and receipt["initial_manifest_matches"] and receipt["original_38_probe_matches"] and raw_matches and all(item["matches"] for item in new_records + source + old_records + preserved + initial_records) and all(item["working_git_object_equal"] for item in source)
    receipt["passed"] = passed
    (OUT / "frozen_evidence_values.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "new_artifacts": len(new_records), "new_source": len(source), "old_artifacts": len(old_records), "old_current_preserved": len(preserved), "initial_review_files": len(initial_records), "probe_sha256": sha(probe), "raw_failure": receipt["raw_failure"]}, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
