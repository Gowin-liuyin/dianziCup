"""Independently verify author raw manifests, Git blobs, and unchanged upstream tests."""

import hashlib
import json
import subprocess

from review_runner import ROOT, RUN, now

CODE = "c842333fe56a4ab3018a3216a8ddcd6a34639ae1"
MATERIAL = "99fec14d1a64f9c5adaa5beb294e804da3e1d18d"
AUTHOR_RUN = "reports/runs/recovery_r11_r08_forward_migrations_20261016"
AUTHOR_ROOT = ROOT.parent / "r11-r08-forward-migrations"


def blob(commit, path):
    return subprocess.run(
        ["git", "show", commit + ":" + path], cwd=ROOT, capture_output=True, check=True
    ).stdout


def sha(content):
    return hashlib.sha256(content).hexdigest()


def main():
    manifest_path = AUTHOR_RUN + "/artifact_manifest.json"
    manifest_raw = blob(MATERIAL, manifest_path)
    assert sha(manifest_raw) == "7a3adc9c434122f2e979eeb0b967eff9b5fe3f98a1db90c6c205f29f37b877ad"
    manifest = json.loads(manifest_raw)
    verified = []
    for entry in manifest["files"]:
        raw = (AUTHOR_ROOT / entry["path"]).read_bytes()
        checkout = (ROOT / entry["path"]).read_bytes()
        git_bytes = blob(MATERIAL, entry["path"])
        assert len(raw) == entry["length"] and sha(raw) == entry["raw_sha256"]
        assert git_bytes.replace(b"\r\n", b"\n") == raw.replace(b"\r\n", b"\n")
        assert checkout.replace(b"\r\n", b"\n") == git_bytes.replace(b"\r\n", b"\n")
        verified.append(
            {
                "path": entry["path"],
                "raw_size": len(raw),
                "git_size": len(git_bytes),
                "raw_sha256": sha(raw),
                "git_sha256": sha(git_bytes),
                "checkout_size": len(checkout),
                "checkout_sha256": sha(checkout),
                "git_equals_raw": git_bytes == raw,
            }
        )
    assert len(verified) == 132
    source = json.loads(blob(MATERIAL, AUTHOR_RUN + "/source_manifest.json"))
    upstream = []
    for entry in source["upstream_sources"]:
        code_bytes = blob(CODE, entry["path"])
        source_bytes = blob(entry["material_commit"], entry["path"])
        material_bytes = blob(MATERIAL, entry["path"])
        assert source_bytes == code_bytes == material_bytes
        assert sha(code_bytes) == entry["git_blob_sha256"]
        raw = (ROOT / entry["path"]).read_bytes()
        upstream.append(
            {
                "path": entry["path"],
                "upstream": entry["material_commit"],
                "blob_sha256": sha(code_bytes),
                "blob_size": len(code_bytes),
                "raw_size": len(raw),
                "raw_sha256": sha(raw),
            }
        )
    assert len(upstream) == 8
    tests = []
    for commit in (
        "bc8798cf5efc81e210a429884930ca545af43ad8",
        "a76374ca9200945441a83421050eceef00db47d8",
    ):
        paths = (
            subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", commit, "backend/tests"],
                cwd=ROOT,
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .splitlines()
        )
        selected = [
            path
            for path in paths
            if any(
                key in path
                for key in (
                    "test_t24_asset_inventory",
                    "test_r11_inventory",
                    "test_r11_manifest",
                    "test_r08_aggregate",
                    "test_r08_cache_ttl",
                )
            )
        ]
        for path in selected:
            old = blob(commit, path)
            current = blob(MATERIAL, path)
            assert old == current
            tests.append(
                {
                    "path": path,
                    "upstream": commit,
                    "blob_size": len(old),
                    "blob_sha256": sha(old),
                    "matches": True,
                }
            )
    changed_source = (
        subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                CODE,
                MATERIAL,
                "backend",
                "contracts",
                "fixtures",
                "progress",
            ],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .splitlines()
    )
    assert changed_source == []
    author_receipts = json.loads(
        "[" + ",".join((ROOT / AUTHOR_RUN / "commands.jsonl").read_text().splitlines()) + "]"
    )
    reds = [entry for entry in author_receipts if entry["exit_code"] != 0]
    attributes = blob(MATERIAL, AUTHOR_RUN + "/.gitattributes").decode()
    assert "*.json -text whitespace=trailing-space,space-before-tab,cr-at-eol" in attributes
    assert "*.jsonl -text whitespace=trailing-space,space-before-tab,cr-at-eol" in attributes
    record = {
        "observed_at": now(),
        "code_sha": CODE,
        "material_sha": MATERIAL,
        "manifest_size": len(manifest_raw),
        "manifest_sha256": sha(manifest_raw),
        "raw_count": len(verified),
        "raw_verified": verified,
        "upstream_sources": upstream,
        "upstream_tests": tests,
        "material_backend_contract_fixture_progress_diff": changed_source,
        "author_reds_preserved": reds,
        "author_local_attributes": attributes,
    }
    (RUN / "material_audit.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "raw_count": len(verified),
                "upstream_source_count": len(upstream),
                "original_test_comparisons": len(tests),
                "author_red_count": len(reds),
            }
        )
    )


if __name__ == "__main__":
    main()
