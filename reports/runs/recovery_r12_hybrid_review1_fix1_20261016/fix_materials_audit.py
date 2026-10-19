"""Verify frozen Fix1 blobs and retain all original author/reviewer evidence byte-for-byte."""

import json
from pathlib import Path

from review_runner import CODE, MATERIALS, ROOT, RUN, git, sha, stamp


def main() -> None:
    path = ROOT / "reports/runs/recovery_r12_hybrid_fix1_20261016/fix_manifest.json"
    assert sha(path.read_bytes()) == "5afd7a75e86afd0635bb0b4befa216244931775a2e48fd71224ad10d75d32b50"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    sources = []
    for item in manifest["source_blobs"]:
        name = item["path"]
        blob = git("show", f"{CODE}:{name}")
        assert sha(blob) == item["sha256"] and blob == (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        assert blob == git("show", f"{MATERIALS}:{name}")
        sources.append(item)
    for item in manifest["unchanged_authority_sources"]:
        name = item["path"]
        blob = git("show", f"{CODE}:{name}")
        assert sha(blob) == item["sha256"] and blob == git("show", f"a43d25e64dd00eaec63521c9457c7fa2228b8799:{name}")
    materials = []
    for item in manifest["materials"]:
        name = item["path"]
        raw = (ROOT / name).read_bytes()
        blob = git("show", f"{MATERIALS}:{name}")
        assert sha(raw) == item["sha256"] or sha(raw.replace(b"\r\n", b"\n")) == item["lf_sha256"]
        assert raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
        materials.append(dict(path=name, raw_sha256=sha(raw), git_sha256=sha(blob)))
    historical = git("ls-tree", "-r", "--name-only", "a43d25e64dd00eaec63521c9457c7fa2228b8799", "reports/runs/recovery_r12_hybrid_retrieval_20261016/", "reports/tasks/R12-hybrid-retrieval.md").decode().splitlines()
    for name in historical:
        assert git("show", f"a43d25e64dd00eaec63521c9457c7fa2228b8799:{name}") == git("show", f"{MATERIALS}:{name}")
    previous_review = Path("D:/wt/r12-hybrid-review1")
    old_manifest_path = previous_review / "reports/runs/recovery_r12_hybrid_review1_20261016/review_manifest.json"
    old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    assert sha(old_manifest_path.read_bytes()) == "47acc1c2e549cea6fcf7ebadf3e31ab5fcc06d86fee3b7a1c29cb0889b3f591f"
    for item in old_manifest["entries"]:
        assert sha((previous_review / item["path"]).read_bytes()) == item["sha256"]
    original = previous_review / "reports/runs/recovery_r12_hybrid_review1_20261016/resource_copy/test_legal_publication_window.py"
    assert sha(original.read_bytes()) == "b55f8ca4e2060d5ee541351b92cd7c0653a6d988bb23cac877390864f7efe852"
    assert original.read_bytes() == (ROOT / "reports/runs/recovery_r12_hybrid_fix1_20261016/reviewer_legal_publication_window.original.py.txt").read_bytes()
    raw_dir = ROOT / "reports/runs/recovery_r12_hybrid_fix1_20261016/synthetic_source_blobs"
    raw_entries = [json.loads(line) for line in (raw_dir / "raw_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    for item in raw_entries:
        raw = (raw_dir / (item["sha256"] + ".txt")).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"] and item["data_mode"] == "synthetic"
    receipt = dict(checked_at=stamp(), code_sha=CODE, materials_sha=MATERIALS, manifest_sha256=sha(path.read_bytes()), source_blobs=sources, unchanged_authority_sources=len(manifest["unchanged_authority_sources"]), materials=materials, original_author_files_unchanged=len(historical), original_review_files_unchanged=len(old_manifest["entries"]), raw_entries=len(raw_entries), distinct_synthetic_originals=len({item["sha256"] for item in raw_entries}), status="passed")
    (RUN / "freeze_materials_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key not in {"source_blobs", "materials"}}))


if __name__ == "__main__":
    main()
