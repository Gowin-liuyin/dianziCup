"""Verify old snapshots against their commits and the repair evidence against the new freeze."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
AUTHOR_RUN = RUN.parent / "recovery_r06_repository_community_20261015"
OLD_SHA = "5e952f25d7a1c03296e1a8801a757c9c0317af99"
CODE_SHA = "d4e22fab7ad4be7bb6281d5d8dd9db3ea53729a6"


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=WORKTREE)


def main() -> None:
    old_manifest = json.loads(
        (AUTHOR_RUN / "evidence_commit_inventory.json").read_bytes()
    )
    for entry in old_manifest:
        body = git("cat-file", "blob", f"{OLD_SHA}:{entry['path']}")
        assert len(body) == entry["size_bytes"] and digest(body) == entry["sha256"]
        if entry["path"].startswith("reports/runs/"):
            assert (WORKTREE / entry["path"]).read_bytes() == body
    old_run_files = (
        git(
            "ls-tree",
            "-r",
            "--name-only",
            OLD_SHA,
            "--",
            "reports/runs/recovery_r06_repository_community_20261015",
        )
        .decode()
        .splitlines()
    )
    for file in old_run_files:
        assert git("cat-file", "blob", f"{OLD_SHA}:{file}") == git(
            "cat-file", "blob", f"HEAD:{file}"
        )
    new_files = (
        git(
            "diff",
            "--name-only",
            OLD_SHA,
            "HEAD",
            "--",
            "reports/runs/recovery_r06_repository_community_20261015",
        )
        .decode()
        .splitlines()
    )
    new_manifest = json.loads((AUTHOR_RUN / "null_fix_inventory.json").read_bytes())
    for entry in new_manifest:
        body = (WORKTREE / entry["path"]).read_bytes()
        assert len(body) == entry["size_bytes"] and digest(body) == entry["sha256"]
        committed_body = git("cat-file", "blob", f"HEAD:{entry['path']}")
        if entry["path"].startswith("reports/runs/"):
            assert committed_body == body
        else:
            assert entry["path"] == "reports/tasks/R06-repository-community.md"
            assert committed_body.replace(b"\r\n", b"\n") == body.replace(
                b"\r\n", b"\n"
            )
    for file in new_files:
        assert git("cat-file", "blob", f"HEAD:{file}") == (WORKTREE / file).read_bytes()
    provenance = json.loads((AUTHOR_RUN / "null_fix_provenance.json").read_bytes())
    assert provenance["code_sha"] == CODE_SHA
    assert (
        git("rev-parse", f"{CODE_SHA}^{{tree}}").decode().strip()
        == provenance["code_tree"]
    )
    assert git("diff", "--name-only", CODE_SHA, "HEAD", "--", "backend") == b""
    original_test = (RUN / "test_independent_boundaries.py").read_bytes()
    assert digest(original_test) == provenance["independent_probe"]["sha256"]
    assert (
        original_test
        == (AUTHOR_RUN / "null_fix_independent_boundaries.original.py").read_bytes()
    )
    assert (
        original_test
        == Path(
            "D:/dianzi/reports/runs/recovery_r06_repository_community_review_1_20261015/test_independent_boundaries.py"
        ).read_bytes()
    )
    assert provenance["report_sha256"] == digest(
        (WORKTREE / "reports/tasks/R06-repository-community.md").read_bytes()
    )
    summary: dict[str, object] = {
        "old_sha": OLD_SHA,
        "old_manifest_rows_verified_against_old_commit": len(old_manifest),
        "old_run_git_blobs_unchanged": len(old_run_files),
        "new_run_git_blobs_equal_checkout": len(new_files),
        "new_manifest_rows_verified": len(new_manifest),
        "new_report_hash": provenance["report_sha256"],
        "new_report_git_blob_hash": digest(
            git("cat-file", "blob", "HEAD:reports/tasks/R06-repository-community.md")
        ),
        "old_report_hash": digest(
            git(
                "cat-file",
                "blob",
                f"{OLD_SHA}:reports/tasks/R06-repository-community.md",
            )
        ),
        "independent_25_original_bytes_sha256": digest(original_test),
        "code_unchanged_after_d4e22fab": True,
        "test_counts": {},
        "source_only_traces": {},
    }
    for path in RUN.glob("*.junit.xml"):
        document = ET.fromstring(path.read_bytes())
        cases = list(document.iter("testcase"))
        fail = [
            case.attrib["name"] for case in cases if case.find("failure") is not None
        ]
        error = [
            case.attrib["name"] for case in cases if case.find("error") is not None
        ]
        skip = [
            case.attrib["name"] for case in cases if case.find("skipped") is not None
        ]
        summary["test_counts"][path.name] = {
            "tests": len(cases),
            "passed": len(cases) - len(fail) - len(error) - len(skip),
            "failures": fail,
            "errors": error,
            "skipped": skip,
        }
    for path in RUN.glob("cbm_trace_*.log"):
        result = json.loads(path.read_bytes())
        result = result.get("structuredContent") or json.loads(
            result["content"][0]["text"]
        )
        summary["source_only_traces"][path.stem] = {
            "function": result["function"],
            "callers_total": result["callers_total"],
            "callers": result["callers"],
        }
    (RUN / "repair_provenance_verification.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
