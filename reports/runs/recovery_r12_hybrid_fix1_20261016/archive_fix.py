"""Freeze the Must1 package and prove historical author/reviewer evidence is unchanged."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE = "ba1548d591d2b341e61a230f1cdd5bd387f3235b"
PREVIOUS = "a43d25e64dd00eaec63521c9457c7fa2228b8799"
REVIEW = Path("D:/wt/r12-hybrid-review1")


def git_blob(revision: str, name: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "blob", f"{revision}:{name}"], cwd=ROOT)


def main() -> int:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", PREVIOUS, CODE], cwd=ROOT)
        .decode()
        .splitlines()
    )
    source_blobs = []
    for name in changed:
        content = git_blob(CODE, name)
        assert (ROOT / name).read_bytes().replace(b"\r\n", b"\n") == content
        source_blobs.append({"path": name, "sha256": hashlib.sha256(content).hexdigest()})
    unchanged_sources = []
    for name in (
        "backend/src/ai_intel/retrieval/service.py",
        "backend/src/ai_intel/knowledge/persistence.py",
        "backend/src/ai_intel/knowledge/revisions.py",
        "backend/src/ai_intel/knowledge/event_linking.py",
        "backend/src/ai_intel/ingestion/catalog_documents.py",
        "backend/src/ai_intel/api/knowledge_read_service.py",
        "backend/src/ai_intel/api/auth_state.py",
        "backend/tests/integration/test_t30_hybrid_retrieval.py",
    ):
        content = git_blob(CODE, name)
        assert content == git_blob(PREVIOUS, name)
        assert (ROOT / name).read_bytes().replace(b"\r\n", b"\n") == content
        unchanged_sources.append({"path": name, "sha256": hashlib.sha256(content).hexdigest()})
    original_run = "reports/runs/recovery_r12_hybrid_retrieval_20261016/"
    historical = (
        subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                PREVIOUS,
                original_run,
                "reports/tasks/R12-hybrid-retrieval.md",
            ],
            cwd=ROOT,
        )
        .decode()
        .splitlines()
    )
    for name in historical:
        raw = (ROOT / name).read_bytes()
        assert raw == git_blob(PREVIOUS, name) or raw.replace(b"\r\n", b"\n") == git_blob(
            PREVIOUS, name
        )
    original = (
        REVIEW
        / "reports/runs/recovery_r12_hybrid_review1_20261016/resource_copy"
        / "test_legal_publication_window.py"
    ).read_bytes()
    assert (
        hashlib.sha256(original).hexdigest()
        == "b55f8ca4e2060d5ee541351b92cd7c0653a6d988bb23cac877390864f7efe852"
    )
    assert (RUN / "reviewer_legal_publication_window.original.py.txt").read_bytes() == original
    review_report = (
        REVIEW / "reports/reviews/recovery/G-D-R12-hybrid-retrieval-review-1.md"
    ).read_bytes()
    assert (
        hashlib.sha256(review_report).hexdigest()
        == "cdfeb41e48afa73ba3ddaf29249b304d43d67ca8cb3237fce648e596bd2fb8f3"
    )
    archived = RUN / "synthetic_source_blobs"
    entries = [
        json.loads(line)
        for line in (archived / "raw_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    for entry in entries:
        body = (archived / (entry["sha256"] + ".txt")).read_bytes()
        assert entry["data_mode"] == "synthetic"
        assert (
            len(body) == entry["size_bytes"] and hashlib.sha256(body).hexdigest() == entry["sha256"]
        )
    tests = {}
    for path in sorted(RUN.glob("*.xml")):
        document = ET.parse(path).getroot()
        tests[path.name] = {
            "tests": len(list(document.iter("testcase"))),
            "failures": len(list(document.iter("failure"))),
            "errors": len(list(document.iter("error"))),
            "skipped": len(list(document.iter("skipped"))),
        }
    assert tests["must1_red.xml"]["failures"] == 4
    assert tests["frozen_integration.xml"] == {
        "tests": 31,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    assert tests["frozen_fixture.xml"] == {"tests": 64, "failures": 0, "errors": 0, "skipped": 0}
    captured = subprocess.run(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        capture_output=True,
        timeout=15,
    )
    assert captured.returncode == 0
    connection = json.loads(captured.stdout)
    password = make_url(connection["TEST_DATABASE_URL"]).password or ""
    credentials = [connection["TEST_DATABASE_URL"], password]
    credentials.extend(password[index : index + 8] for index in range(len(password) - 7))
    excluded = {"fix_manifest.json", "archive_fix.log", "archive_fix.command.json"}
    files = sorted(
        path
        for path in RUN.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.name not in excluded
    )
    files.append(ROOT / "reports/tasks/R12-hybrid-retrieval-fix1.md")
    materials = []
    for path in files:
        raw = path.read_bytes()
        assert not any(value and value.encode() in raw for value in credentials), (
            "credential material found"
        )
        materials.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
            }
        )
    manifest = {
        "code_sha": CODE,
        "previous_materials_sha": PREVIOUS,
        "started_at": started,
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "source_blobs": source_blobs,
        "unchanged_authority_sources": unchanged_sources,
        "original_author_files_unchanged": len(historical),
        "reviewer_source_and_report": "unchanged",
        "raw_entries": len(entries),
        "distinct_synthetic_originals": len({entry["sha256"] for entry in entries}),
        "raw_verification": "passed",
        "test_counts": tests,
        "credential_findings": 0,
        "materials": materials,
        "excluded": sorted(excluded),
    }
    destination = RUN / "fix_manifest.json"
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "code_sha": CODE,
                "materials": len(materials),
                "historical_unchanged": len(historical),
                "credential_findings": 0,
                "manifest_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
