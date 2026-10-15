"""Verify frozen Git blobs and synthetic originals, then hash and scan this package only."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CODE = "f316a7aa432d6f730fa49189814c2559be8b6db4"
BASE = "e310f7735bd499c4d9fbcefe8a644e2309a16a62"


def main() -> int:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    names = (
        subprocess.check_output(["git", "diff", "--name-only", BASE, CODE], cwd=ROOT)
        .decode()
        .splitlines()
    )
    blobs = []
    for name in names:
        blob_id = (
            subprocess.check_output(["git", "rev-parse", f"{CODE}:{name}"], cwd=ROOT)
            .decode()
            .strip()
        )
        content = subprocess.check_output(["git", "cat-file", "blob", blob_id], cwd=ROOT)
        local = (ROOT / name).read_bytes()
        assert local.replace(b"\r\n", b"\n") == content, "frozen source blob differs"
        blobs.append(
            {
                "path": name,
                "git_blob": blob_id,
                "git_blob_sha256": hashlib.sha256(content).hexdigest(),
                "worktree_sha256": hashlib.sha256(local).hexdigest(),
            }
        )
    archive = RUN / "synthetic_source_blobs"
    entries = [
        json.loads(line)
        for line in (archive / "raw_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    for entry in entries:
        assert entry["data_mode"] == "synthetic"
        body = (archive / (entry["sha256"] + ".txt")).read_bytes()
        assert len(body) == entry["size_bytes"]
        assert hashlib.sha256(body).hexdigest() == entry["sha256"]
    counts = {}
    for path in sorted(RUN.glob("*.xml")):
        suites = ET.parse(path).getroot()
        tests = list(suites.iter("testcase"))
        counts[path.name] = {
            "tests": len(tests),
            "failures": len(list(suites.iter("failure"))),
            "errors": len(list(suites.iter("error"))),
            "skipped": len(list(suites.iter("skipped"))),
        }
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
        check=False,
        timeout=15,
    )
    assert captured.returncode == 0, "authorized secret scan reference unavailable"
    connection = json.loads(captured.stdout)
    password = make_url(connection["TEST_DATABASE_URL"]).password or ""
    secrets = [connection["TEST_DATABASE_URL"], password]
    secrets.extend(password[index : index + 8] for index in range(len(password) - 7))
    files = sorted(
        path
        for path in RUN.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name
        not in {
            "materials_manifest.json",
            "archive_evidence.log",
            "archive_evidence.command.json",
            "final_archive.log",
            "final_archive.command.json",
        }
    )
    files += [
        ROOT / "reports/tasks/R12-hybrid-retrieval.md",
        ROOT / "docs/design/recovery/R12-hybrid-index-proposal.md",
    ]
    findings = []
    materials = []
    for path in files:
        content = path.read_bytes()
        if any(secret and secret.encode() in content for secret in secrets):
            findings.append(path.relative_to(ROOT).as_posix())
        materials.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "lf_sha256": hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest(),
            }
        )
    assert not findings, "credential scan found content in own package"
    manifest = {
        "started_at": started,
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "code_sha": CODE,
        "baseline_sha": BASE,
        "source_blobs": blobs,
        "synthetic_manifest_entries": len(entries),
        "synthetic_distinct_originals": len({entry["sha256"] for entry in entries}),
        "source_blob_verification": "passed",
        "credential_findings": findings,
        "test_counts": counts,
        "materials": materials,
        "excluded": (
            "self manifest/its command log, Python cache; no secret values or private originals"
        ),
    }
    destination = RUN / "materials_manifest.json"
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "code_sha": CODE,
                "materials_count": len(materials),
                "raw_entries": len(entries),
                "source_blobs_verified": len(blobs),
                "credential_findings": 0,
                "manifest_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
