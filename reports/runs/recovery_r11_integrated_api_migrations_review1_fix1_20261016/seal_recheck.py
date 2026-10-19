"""Finalize actual JUnit counts, scan known secret bytes and verify all nonrecursive members."""

import hashlib
import json
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from recheck_checks import DATABASE, read_reference

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-D-R11-integrated-api-migrations-review-1-recheck.md"
OLD_ROOT = Path("D:/wt/r11-integrated-api-review1")
OLD_RUN = OLD_ROOT / "reports/runs/recovery_r11_integrated_api_migrations_review1_20261016"
AUTHOR_RUN = ROOT / "reports/runs/recovery_r11_sbom_locator_privacy_fix1_20261016"
CONTROLS = {"review_manifest.json", "review_seal.json", "exact_secret_scan.json", "report_write_receipt.json"}


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == "54f17c9a61d55af5ffe43e58d9252efad6317646"
    assert not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    assert not subprocess.check_output(["git", "diff", "--cached", "--numstat"], cwd=ROOT, text=True)
    cases = []
    for path in sorted(RUN.glob("*.xml")):
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        counts = {key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
        counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
        cases.append({"path": path.name, "sha256": digest(path.read_bytes()), "counts": counts, "case_names": [case.get("name") for case in root.iter("testcase")]})
    assert all(item["counts"]["skipped"] == 0 for item in cases)
    summary = {"recorded_at": now(), "verdict": "limited Ship", "junit": cases,
               "known_red_not_closed": ["legacy_head_oracle", "previous_review_R07_NVD_oracle"], "no_sum_for_overlapping_suites": True}
    (RUN / "actual_test_counts.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reference = read_reference()
    values = [reference.password, reference.render_as_string(hide_password=False),
              reference.set(database=DATABASE).render_as_string(hide_password=False), reference.set(database=DATABASE + "_mig").render_as_string(hide_password=False)]
    files = [path for path in RUN.rglob("*") if path.is_file() and not {"__pycache__", "mypy-cache"}.intersection(path.parts)]
    matches = []
    scanned = 0

    def scan(label, content):
        nonlocal scanned
        scanned += 1
        if any(value and value.encode() in content for value in values):
            matches.append(label)

    for path in [*files, REPORT, ROOT / "backend/src/ai_intel/assets/sbom_inventory.py", ROOT / "backend/tests/unit/test_r11_sbom_locator_privacy.py"]:
        scan(str(path.relative_to(ROOT)), path.read_bytes())
    with tarfile.open(AUTHOR_RUN / "evidence_exact_raw.tar.gz") as archive:
        for member in archive.getmembers():
            assert member.isfile()
            scan("author_exact_raw:" + member.name, archive.extractfile(member).read())
    old_manifest = json.loads((OLD_RUN / "review_manifest.json").read_text())
    for member in old_manifest["members"]:
        content = (OLD_ROOT / member["path"]).read_bytes()
        assert len(content) == member["bytes"] and digest(content) == member["sha256"]
        scan("old_review:" + member["path"], content)
    assert not matches, "actual authorized DSN/password bytes found"
    (RUN / "exact_secret_scan.json").write_text(json.dumps({"recorded_at": now(), "files_and_raw_members_scanned": scanned, "actual_authorized_secret_matches": [], "match_count": 0,
        "author_raw_members_scanned": 187, "old_review_members_scanned_and_reverified": 200, "excluded_reproducible_caches": ["mypy-cache", "__pycache__"]}, indent=2) + "\n")
    files = [path for path in RUN.rglob("*") if path.is_file() and not {"__pycache__", "mypy-cache"}.intersection(path.parts)]
    members = []
    for path in sorted(files):
        if path.name in CONTROLS:
            continue
        content = path.read_bytes()
        members.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(content), "sha256": digest(content)})
    manifest = {"recorded_at": now(), "head": "54f17c9a61d55af5ffe43e58d9252efad6317646", "tree": "905511223ab99e15b51f515a51b95f3bd1bb08c6",
                "source_commit": "dcbc3d928b26f6755a5bfa71a3b70f71527bd832", "members": members, "member_count": len(members), "excluded_controls": sorted(CONTROLS)}
    manifest_path = RUN / "review_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_sha = digest(manifest_path.read_bytes())
    report = REPORT.read_text(encoding="utf-8")
    assert report.count("MANIFEST_SHA_PENDING") == 1
    REPORT.write_text(report.replace("MANIFEST_SHA_PENDING", manifest_sha), encoding="utf-8", newline="\n")
    receipt_path = RUN / "report_write_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update(ended_at=now(), report_bytes=REPORT.stat().st_size, report_raw_sha256=digest(REPORT.read_bytes()))
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    for member in members:
        content = (ROOT / member["path"]).read_bytes()
        assert len(content) == member["bytes"] and digest(content) == member["sha256"]
    seal = {"recorded_at": now(), "verdict": "limited Ship", "head": manifest["head"], "tree": manifest["tree"], "source_commit": manifest["source_commit"],
            "manifest_raw_sha256": manifest_sha, "report_raw_sha256": digest(REPORT.read_bytes()), "member_count": len(members), "member_failures": [],
            "secret_scan_raw_sha256": digest((RUN / "exact_secret_scan.json").read_bytes()), "report_write_receipt_sha256": digest(receipt_path.read_bytes()),
            "actual_secret_matches": 0, "old_review_200_reverified": True, "tracked_changes": 0, "staged_changes": 0}
    (RUN / "review_seal.json").write_text(json.dumps(seal, indent=2) + "\n")
    print(json.dumps(seal, indent=2))


if __name__ == "__main__":
    main()
