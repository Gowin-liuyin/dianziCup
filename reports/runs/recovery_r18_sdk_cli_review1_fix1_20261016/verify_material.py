"""Read-only raw/LF material proof and protected upstream verification."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
AUTHOR_RUN = ROOT / "reports/runs/recovery_r18_sdk_client_fix1_20261016"
MATERIAL = "0601f469f1a90b9061ca77f718aa845051e76641"
SOURCE = "6d85742b0114cc5e304e88b2aa930755ccce9bc9"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def main() -> int:
    manifest_path = AUTHOR_RUN / "artifact_manifest_material_repair.json"
    manifest_raw = manifest_path.read_bytes()
    manifest_git = git("show", f"{MATERIAL}:{manifest_path.relative_to(ROOT).as_posix()}")
    manifest = json.loads(manifest_raw)
    fresh_proof_path = Path(
        "D:/wt/r18-sdk-client-fix1/reports/runs/recovery_r18_sdk_client_fix1_20261016/"
        "fresh_material_checkout_byte_proof.json"
    )
    proof_raw = fresh_proof_path.read_bytes()
    fresh_proof = json.loads(proof_raw)
    proof_files = {item["path"]: item for item in fresh_proof["files"]}
    members = []
    for item in manifest["files"]:
        raw = (ROOT / item["path"]).read_bytes()
        blob = git("show", f"{MATERIAL}:{item['path']}")
        mode = item["git_byte_mode"]
        expected_fresh = proof_files[item["path"]]
        matches = (
            digest(raw) == item["sha256"]
            if mode == "exact_raw"
            else raw.replace(b"\r\n", b"\n") == blob
        )
        members.append(
            {
                "path": item["path"],
                "declared_mode": mode,
                "original_declared_sha256": item["sha256"],
                "fresh_raw_sha256": digest(raw),
                "fresh_lf_sha256": digest(raw.replace(b"\r\n", b"\n")),
                "material_git_sha256": digest(blob),
                "matches_mode": matches,
                "matches_prior_fresh_proof_git": digest(blob) == expected_fresh["git_blob_sha256"],
                "source_sha": SOURCE if item["path"].startswith("sdk/python/") else None,
            }
        )
    old110 = json.loads((AUTHOR_RUN / "artifact_manifest.json").read_bytes())
    author_root = Path("D:/wt/r18-sdk-client-fix1")
    protected_current = [
        {
            "path": item["path"],
            "author_raw_sha256": digest((author_root / item["path"]).read_bytes()),
            "matches": digest((author_root / item["path"]).read_bytes()) == item["sha256"],
        }
        for item in old110["files"]
    ]
    upstream_results = []
    for checkout, relative, count in (
        (
            Path("D:/wt/r18-client-sdk"),
            "reports/runs/recovery_r18_client_sdk_20261016/artifact_manifest.json",
            86,
        ),
        (
            Path("D:/wt/r18-sdk-client-review1"),
            "reports/runs/recovery_r18_sdk_cli_review1_20261016/artifact_manifest.json",
            83,
        ),
    ):
        upstream_raw = (checkout / relative).read_bytes()
        upstream = json.loads(upstream_raw)
        details = [
            {
                "path": item["path"],
                "matches": digest((checkout / item["path"]).read_bytes()) == item["raw_sha256"],
            }
            for item in upstream["artifacts"]
        ]
        upstream_results.append(
            {
                "checkout": str(checkout),
                "member_count": count,
                "manifest_sha256": digest(upstream_raw),
                "files": details,
                "all_unchanged": len(details) == count and all(item["matches"] for item in details),
            }
        )
    original_probe = Path(
        "D:/wt/r18-sdk-client-review1/reports/runs/recovery_r18_sdk_cli_review1_20261016/"
        "test_independent_boundaries.py"
    ).read_bytes()
    copied_probe = (RUN / "test_independent_boundaries.py").read_bytes()
    frozen_copy = (AUTHOR_RUN / "test_independent_boundaries.py").read_bytes()
    author_copy = (
        author_root / "reports/runs/recovery_r18_sdk_client_fix1_20261016/"
        "test_independent_boundaries.py"
    ).read_bytes()
    report_path = ROOT / "reports/tasks/R18-sdk-client-fix1-material-repair.md"
    source_diff = subprocess.run(
        ["git", "diff", "--exit-code", SOURCE, MATERIAL, "--", "sdk/python"],
        cwd=ROOT,
        capture_output=True,
    )
    result = {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "material_tree": git("rev-parse", f"{MATERIAL}^{{tree}}").decode().strip(),
        "source_sha": SOURCE,
        "source_tree": git("rev-parse", f"{SOURCE}^{{tree}}").decode().strip(),
        "manifest_raw_sha256": digest(manifest_raw),
        "manifest_git_lf_sha256": digest(manifest_git),
        "report_raw_sha256": digest(report_path.read_bytes()),
        "fresh_prior_proof_sha256": digest(proof_raw),
        "material_members": members,
        "member_modes": dict(Counter(item["declared_mode"] for item in members)),
        "original110_raw_unchanged": all(item["matches"] for item in protected_current),
        "original110_files": protected_current,
        "protected_upstream169": upstream_results,
        "copied65_sha256": digest(copied_probe),
        "copied65_review_original_author_raw_identical": copied_probe
        == original_probe
        == author_copy,
        "copied65_fresh_lf_identical": frozen_copy.replace(b"\r\n", b"\n")
        == copied_probe.replace(b"\r\n", b"\n"),
        "cli11_copy_identical": (RUN / "test_cli_fix1_regressions.py").read_bytes()
        == (AUTHOR_RUN / "test_cli_fix1_regressions.py").read_bytes(),
        "source_material_sdk_diff_exit": source_diff.returncode,
        "runtime_versions": {
            name: importlib.metadata.version(name)
            for name in (
                "httpx",
                "pydantic",
                "pytest",
                "mypy",
                "ruff",
                "jsonschema",
                "mcp",
                "tiktoken",
            )
        },
        "python_executable": sys.executable,
        "product_credentials_obtained": 0,
    }
    valid = (
        result["head"] == MATERIAL
        and result["source_tree"] == "88018597cb9bb94971edb38d90e4525f6b04a8a4"
        and result["manifest_raw_sha256"]
        == "33c4f94a47e771408f5bf724d67135810a72a09857b89722502ae2118b78ff81"
        and result["manifest_git_lf_sha256"]
        == "86f2ef7091b87f3173a80c85797f66ba95e4dc082596954a92aed54562e3a189"
        and result["report_raw_sha256"]
        == "975d055fb5d9ebd0e5d9dae0d71971ffb9915689968da9503555744f88796257"
        and result["fresh_prior_proof_sha256"]
        == "9d7db9b1996596ee96fc414aa5d23c4f1a0b9b3e9b7dfcd39de5b5555fb34c92"
        and len(members) == 144
        and all(item["matches_mode"] and item["matches_prior_fresh_proof_git"] for item in members)
        and result["original110_raw_unchanged"]
        and result["copied65_review_original_author_raw_identical"]
        and result["copied65_fresh_lf_identical"]
        and result["cli11_copy_identical"]
        and source_diff.returncode == 0
        and all(item["all_unchanged"] for item in upstream_results)
    )
    result["all_checks_passed"] = valid
    (RUN / "independent_material_proof.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "all_checks_passed": valid,
                "member_count": len(members),
                "modes": result["member_modes"],
                "old169_preserved": all(item["all_unchanged"] for item in upstream_results),
            }
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
