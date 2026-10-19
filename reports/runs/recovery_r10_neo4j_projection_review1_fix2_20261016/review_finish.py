"""Readonly audits, exact JUnit counts, full secret scans and frozen evidence archive."""

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from review_runner import BASE, CODE, ROOT, RUN, TIP, now, receipt, resources

REPORT = ROOT / "reports/reviews/recovery/G-C-R10-neo4j-projection-review-1-recheck2.md"

if sys.argv[1:] == ["audit"]:
    commands = (
        ("rg_actual_callsites", ["rg", "-n", "capture_event_projection|begin_reconciliation|build_graph_apply_handler|read_projection_candidates|Neo4jProjectionStore|graph_apply", "backend/src", "backend/migrations", "scripts", "frontend/src"]),
        ("rg_final_fence", ["rg", "-n", "rows: Sequence|if event_ids|current != manifest|def _epochs|IS :: INTEGER|slot.payload_sha256=edge", "backend/src/ai_intel/knowledge/graph_projection.py", "backend/src/ai_intel/infrastructure/neo4j_projection.py"]),
        ("git_source_diff_check", ["git", "diff", "--check", BASE, TIP, "--", "backend/src", "backend/tests", "reports/tasks/R10-neo4j-projection-fix2.md"]),
    )
    for name, command in commands:
        receipt(name, command, ROOT, dict(os.environ))
    summaries = []
    for path in sorted(RUN.glob("*.xml")):
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        summaries.append({"file": path.name, **{key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")},
            "failed_case_ids": [case.get("name") for case in root.iter("testcase") if case.find("failure") is not None or case.find("error") is not None]})
    (RUN / "junit_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(json.dumps(summaries, indent=2))
elif sys.argv[1:] == ["seal"]:
    assert REPORT.is_file()
    actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert actual == TIP
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    for line in dirty.splitlines():
        path = line[3:].replace("\\", "/")
        assert path.startswith("reports/runs/recovery_r10_neo4j_projection_review1_fix2_20261016/") or path == REPORT.relative_to(ROOT).as_posix()
    url, neo = resources()
    sensitive = (url.render_as_string(hide_password=False), url.set(database="test_dianzi_r10_projection_review1_fix2_20261016").render_as_string(hide_password=False), url.password, url.username, neo["NEO4J_TEST_PASSWORD"])
    files = [path for path in RUN.rglob("*") if path.is_file() and path.name not in ("raw_evidence_manifest.json", "raw_evidence.zip", "final_secret_scan.json")]
    files.append(REPORT)
    findings = []
    classified_public_contexts = []
    base_database_identifier = b"test_" + b"dianzi_r01_" + b"20261014"
    for path in files:
        raw = path.read_bytes()
        if path.name in ("review_runner.py", "prepare_review.py"):
            if base_database_identifier in raw:
                classified_public_contexts.append(path.relative_to(ROOT).as_posix())
                raw = raw.replace(base_database_identifier, b"[public isolated base database identifier]")
        if any(value and value.encode() in raw for value in sensitive):
            findings.append(path.relative_to(ROOT).as_posix())
    assert not findings, "actual private resource value detected"
    scan = {"observed_at": now(), "files_scanned": len(files), "actual_values_checked_in_memory": True,
            "fields": ["exact DSNs", "PG password", "PG login username", "Neo4j password"],
            "actual_value_leak_count": 0, "classified_complete_public_database_identifier_contexts": classified_public_contexts,
            "scope": "entire own run and report; no whole file exclusions"}
    (RUN / "final_secret_scan.json").write_text(json.dumps(scan, indent=2), encoding="utf-8")
    files.append(RUN / "final_secret_scan.json")
    manifest = {"sealed_at": now(), "code_sha": CODE, "materials_sha": TIP, "base_sha": BASE,
                "review_verdict": "Ship (internal projection slice only)", "accepted_or_progress_changed": False, "files": []}
    archive = RUN / "raw_evidence.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as opened:
        for path in sorted(files):
            relative = path.relative_to(ROOT).as_posix()
            raw = path.read_bytes()
            manifest["files"].append({"path": relative, "length_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(), "git_lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
            opened.writestr(relative, raw)
    manifest["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    (RUN / "raw_evidence_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"sealed": True, "files": len(files), "archive_sha256": manifest["archive_sha256"]}))
else:
    raise SystemExit("expected audit or seal")
