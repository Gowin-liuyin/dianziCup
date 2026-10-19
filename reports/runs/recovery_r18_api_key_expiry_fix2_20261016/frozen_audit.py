"""Verify only explicit frozen source and material allowlists, including original probe bytes."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE = "c0428cb9801549c3bc778060153899e4b72028a2"
REVIEW_ROOT = Path("D:/wt/r18-api-key-review1-fix1")
CREDENTIAL_PATH = "backend/src/ai_intel/api/credentials.py"
PROTECTED_PATHS = (
    "AGENTS.md",
    "backend/uv.lock",
    "backend/pyproject.toml",
    "frontend/package-lock.json",
    "backend/src/ai_intel/api/auth_state.py",
    "backend/src/ai_intel/api/authentication.py",
    "backend/src/ai_intel/domain/access.py",
    "backend/tests/conftest.py",
    "contracts/task_manifest.json",
    "contracts/schemas/public_api_v2.json",
    "progress/task_state.json",
    "progress/context_handoff.md",
    "reports/security/recovery_fixture_false_positives.json",
)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def git_bytes(ref: str, relative: str) -> bytes:
    return subprocess.check_output(["git", "show", ref + ":" + relative], cwd=ROOT)


def verify_manifest(directory: str, ref: str, raw_key: str) -> list[dict[str, object]]:
    manifest = json.loads((ROOT / directory / "artifact_manifest.json").read_bytes())
    records = []
    with zipfile.ZipFile(ROOT / directory / "raw_artifacts.zip") as archive:
        for entry in manifest["files"]:
            relative = entry["path"]
            frozen = git_bytes(ref, relative)
            raw = frozen if relative.endswith("raw_artifacts.zip") else archive.read(relative)
            record = {
                "path": relative,
                "frozen_git_match": digest(frozen) == entry["git_blob_sha256"],
                "frozen_raw_match": digest(raw) == entry[raw_key],
                "current_matches_base_git": relative == CREDENTIAL_PATH
                or git_bytes("HEAD", relative) == git_bytes(BASE, relative),
                "credential_change_explicitly_allowed": relative == CREDENTIAL_PATH,
            }
            assert record["frozen_git_match"] and record["frozen_raw_match"]
            assert record["current_matches_base_git"]
            records.append(record)
    return records


def public_signatures(content: bytes) -> dict[str, str]:
    tree = ast.parse(content)
    return {
        node.name: ast.dump(node.args) + ast.dump(node.returns)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"lock_authenticated_principal", "consume_api_key_rate_limit"}
        and node.returns is not None
    }


def main() -> None:
    old_author = verify_manifest(
        "reports/runs/recovery_r18_api_key_credential_20261016",
        "8ae692b5c2824c368b6296481d12695babc717cd",
        "sha256",
    )
    ci_fix1 = verify_manifest(
        "reports/runs/recovery_r18_api_key_ci_fixture_fix1_20261016",
        BASE,
        "raw_sha256",
    )
    protected = [
        {
            "path": path,
            "unchanged_git": git_bytes(BASE, path) == git_bytes("HEAD", path),
            "current_raw_sha256": digest((ROOT / path).read_bytes()),
        }
        for path in PROTECTED_PATHS
    ]
    assert len(old_author) == 88 and len(ci_fix1) == 100 and len(protected) == 13
    assert all(entry["unchanged_git"] for entry in protected)
    caller_paths = subprocess.check_output(
        ["rg", "-l", "lock_authenticated_scope|lock_authenticated_principal", "backend/src"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    callers = [
        {
            "path": path.replace("\\", "/"),
            "unchanged_git": path.replace("\\", "/") == CREDENTIAL_PATH
            or git_bytes(BASE, path.replace("\\", "/"))
            == git_bytes("HEAD", path.replace("\\", "/")),
            "credential_change_explicitly_allowed": path.replace("\\", "/") == CREDENTIAL_PATH,
        }
        for path in caller_paths
    ]
    assert all(entry["unchanged_git"] for entry in callers)
    with zipfile.ZipFile(
        ROOT / "reports/runs/recovery_r18_api_key_credential_20261016/raw_artifacts.zip"
    ) as archive:
        original_pg = archive.read("backend/tests/integration/test_r18_api_key_credentials_pg.py")
    current_pg = git_bytes("HEAD", "backend/tests/integration/test_r18_api_key_credentials_pg.py")
    first_test = b"def test_issuance_only_once_hash_persistence_owner_and_session_compatibility("
    assert (
        original_pg[original_pg.index(first_test) :] == current_pg[current_pg.index(first_test) :]
    )
    assert public_signatures(git_bytes(BASE, CREDENTIAL_PATH)) == public_signatures(
        (ROOT / CREDENTIAL_PATH).read_bytes()
    )
    review_directory = REVIEW_ROOT / "reports/runs/recovery_r18_api_key_review1_fix1_20261016"
    review_manifest = review_directory / "review_manifest.json"
    review_hash = digest(review_manifest.read_bytes())
    assert review_hash == "4705e2c71eeaf100f2fe53422359e80ae5e628eb584b9bd7567956b22c0a713f"
    review_entries = json.loads(review_manifest.read_bytes())["files"]
    assert all(
        digest((REVIEW_ROOT / entry["path"]).read_bytes()) == entry["sha256"]
        for entry in review_entries
    )
    original_probe = (review_directory / "independent_pg_probe.py").read_bytes()
    assert original_probe == (RUN / "independent_pg_probe.py").read_bytes()
    receipt = {
        "old_author_records": old_author,
        "ci_fix1_records": ci_fix1,
        "protected": protected,
        "callers": callers,
        "public_function_signatures_unchanged": True,
        "original_twenty_business_test_bytes_unchanged": True,
        "original_review_manifest_raw_sha256": review_hash,
        "original_review_all_files_unchanged": True,
        "same_probe_exact_raw_sha256": digest(original_probe),
        "same_probe_bytes_unchanged": True,
        "local_attributes": "only own new-run *.log/*.xml/zip binary; root attrs unchanged",
    }
    target = RUN / "frozen_audit_observation.json"
    assert not target.exists()
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "old_author": 88,
                "ci_fix1": 100,
                "protected": 13,
                "caller_files": len(callers),
                "same_probe_bytes_unchanged": True,
            }
        )
    )


if __name__ == "__main__":
    main()
