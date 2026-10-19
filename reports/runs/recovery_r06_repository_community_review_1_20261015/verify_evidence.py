"""Verify frozen bytes, bounded public probe records, and lossless failure archives."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from itertools import pairwise
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
AUTHOR_RUN = RUN.parent / "recovery_r06_repository_community_20261015"
AUTHOR_WORKTREE_RUN = Path(
    "D:/wt/r06-repos/reports/runs/recovery_r06_repository_community_20261015"
)
PREPARATION_RUN = Path(
    "D:/wt/r06-prep-review/reports/runs/recovery_r06_source_preparation_20261015"
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=WORKTREE)


def main() -> None:
    results: dict[str, object] = {}
    raw_results = []
    for label in (
        "avid_01",
        "avid_02",
        "avid_03",
        "ollama_release_real",
        "osv_ollama_real",
    ):
        body = (AUTHOR_RUN / f"{label}.body").read_bytes()
        metadata = json.loads((AUTHOR_RUN / f"{label}.metadata.json").read_bytes())
        assert digest(body) == metadata["body_sha256"]
        assert len(body) == metadata.get(
            "size_bytes", metadata.get("response_size_bytes")
        )
        raw_results.append(
            {
                "label": label,
                "sha256": digest(body),
                "bytes": len(body),
                "hash_matches": True,
            }
        )
    results["source_raw_hashes"] = raw_results
    for label, preparation_label in (
        ("ollama_release_real", "doh_04_ollama_release"),
        ("osv_ollama_real", "doh_01_osv_ollama"),
    ):
        assert (AUTHOR_RUN / f"{label}.body").read_bytes() == (
            PREPARATION_RUN / f"{preparation_label}.body"
        ).read_bytes()
    results["preparation_raw_copies_equal"] = True
    inspection = json.loads((AUTHOR_RUN / "avid_record_inspection.json").read_bytes())
    blob_results = []
    for index, entry in enumerate(inspection, start=2):
        wrapper = json.loads((AUTHOR_RUN / f"avid_{index:02}.body").read_bytes())
        body = (AUTHOR_RUN / f"avid_{index:02}.record.json").read_bytes()
        assert wrapper["encoding"] == "base64"
        decoded = base64.b64decode(wrapper["content"].replace("\n", ""), validate=True)
        assert decoded == body
        blob_sha1 = hashlib.sha1(
            b"blob " + str(len(body)).encode() + b"\0" + body
        ).hexdigest()
        assert blob_sha1 == wrapper["sha"] == entry["git_blob_sha1"]
        assert len(body) == wrapper["size"] == entry["body_size_bytes"]
        assert digest(body) == entry["sha256"]
        document = json.loads(body)
        assert document == entry["body"]
        blob_results.append(
            {
                "id": document["metadata"]["vuln_id"],
                "git_blob_sha1": blob_sha1,
                "sha256": digest(body),
                "bytes": len(body),
                "dates": [document["published_date"], document["last_modified_date"]],
                "reference_count": len(document["references"]),
            }
        )
    results["avid_blob_integrity"] = blob_results
    probe = json.loads((AUTHOR_RUN / "avid_probe_summary.json").read_bytes())
    assert len(probe) == 3
    starts = [datetime.fromisoformat(item["started_at"]) for item in probe]
    assert all(
        (next_start - start).total_seconds() >= 7
        for start, next_start in pairwise(starts)
    )
    for item in probe:
        assert item["method"] == "GET" and item["credentials_used"] is False
        assert item["max_response_bytes"] == 2097152 and item["timeout_seconds"] == 15
        assert item["redirects"] == item["retries"] == 0 and item["status"] == 200
    results["probe"] = {
        "requests": 3,
        "status_200": 3,
        "starts": [item["started_at"] for item in probe],
        "remaining_headers": [
            item["headers"]["X-RateLimit-Remaining"] for item in probe
        ],
        "utc_date_headers": [item["headers"]["Date"] for item in probe],
        "reviewer_new_network_requests": 0,
    }
    archives = []
    for entry in json.loads(
        (AUTHOR_RUN / "lossless_failure_archives.json").read_bytes()
    ):
        archive = (AUTHOR_RUN / entry["archive_path"]).read_bytes()
        original = gzip.decompress(archive)
        author_original = (AUTHOR_WORKTREE_RUN / entry["original_path"]).read_bytes()
        assert (
            len(archive) == entry["archive_size_bytes"]
            and digest(archive) == entry["archive_sha256"]
        )
        assert (
            len(original) == entry["original_size_bytes"]
            and digest(original) == entry["original_sha256"]
        )
        assert author_original == original
        result = {
            **entry,
            "decompressed_matches_original": True,
            "author_untracked_file_matches": True,
        }
        if entry["original_path"].endswith(".xml"):
            document = ET.fromstring(original)
            result["testsuites"] = [
                suite.attrib for suite in document.iter("testsuite")
            ]
            result["failed_test_names"] = [
                case.attrib["name"]
                for case in document.iter("testcase")
                if case.find("failure") is not None
            ]
        archives.append(result)
    results["lossless_archives"] = archives
    files = (
        git("diff", "--name-only", "1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc...HEAD")
        .decode()
        .splitlines()
    )
    committed_raw_count = 0
    for file in files:
        if file.startswith("reports/runs/recovery_r06_repository_community_20261015/"):
            assert (
                git("cat-file", "blob", f"HEAD:{file}")
                == (WORKTREE / file).read_bytes()
            )
            committed_raw_count += 1
    results["frozen_run_git_blobs_equal_worktree_bytes"] = committed_raw_count
    assert (
        git(
            "diff",
            "--name-only",
            "e5b48ae4db4c1e77a08d830ce12eb63ab3d49c39",
            "HEAD",
            "--",
            "backend",
        )
        == b""
    )
    results["code_unchanged_after_e5b48ae"] = True
    results["author_untracked_retention_status"] = (
        subprocess.check_output(
            [
                "git",
                "status",
                "--short",
                "--untracked-files=all",
                "--",
                "reports/runs/recovery_r06_repository_community_20261015/focused_post_implementation.log",
                "reports/runs/recovery_r06_repository_community_20261015/focused_post_implementation.junit.xml",
            ],
            cwd="D:/wt/r06-repos",
        )
        .decode()
        .splitlines()
    )
    results["attributes"] = (
        git(
            "check-attr",
            "text",
            "whitespace",
            "--",
            "reports/runs/recovery_r06_repository_community_20261015/avid_02.record.json",
            "backend/src/ai_intel/ingestion/sources/osv.py",
            "backend/tests/unit/test_r06_osv_range_boundaries.py",
        )
        .decode()
        .splitlines()
    )
    results["license_evidence"] = {
        "read_only_preparation_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd="D:/wt/r06-prep-review"
        )
        .decode()
        .strip(),
        "notes_sha256": digest(
            (PREPARATION_RUN / "web_research_notes.md").read_bytes()
        ),
        "source_reference": "https://github.com/avidml/avid-db/blob/main/LICENSE",
        "scope": "Prepared MIT source notice evidence; no new external check or public redistribution of linked third-party papers",
    }
    (RUN / "evidence_verification.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
