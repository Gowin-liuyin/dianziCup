"""Build an exact-match proposal only for manually established test and redaction literals."""

import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone

from inspect_candidates import ROOT, RUN, security_scan


def git_output(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments],cwd=ROOT,text=True).strip()


def snapshot(relative: str) -> dict[str, object]:
    path = ROOT / relative
    raw = path.read_bytes()
    return {"path":relative,"sha256":hashlib.sha256(raw).hexdigest(),"observed_at":datetime.now(timezone.utc).isoformat(),"blob_sha":git_output("hash-object","--",relative)}


def main() -> None:
    metadata = json.loads((RUN / "unclassified_metadata.json").read_text(encoding="utf-8"))
    head = git_output("rev-parse","HEAD")
    records = []
    snapshots = {}
    for item in metadata["occurrences"]:
        relative = item["path"]
        if "/venv/" in relative:
            continue
        raw = (ROOT / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["raw_sha256"]
        content = raw.decode("utf-8",errors="ignore").replace("\r\n","\n").replace("\r","\n")
        match = security_scan.PATTERNS[item["pattern_id"]].match(content,item["start"])
        assert match is not None and match.end() == item["end"]
        span = match.group(0)
        quote_start = min(index for index, character in enumerate(span) if character in "\"'")
        value = span[quote_start+1:-1]
        assert hashlib.sha256(value.encode()).hexdigest() == item["match_sha256"]
        evidence_type = ""
        report_path = ""
        candidate_commit = head
        source_path, source_line = relative, item["line"]
        if relative == "frontend/src/api/question-client.test.ts":
            evidence_type = "isolated_vitest_fetch_stub_csrf_literal"
        elif "source_rate_candidate_parser_red.log" in relative:
            source_path = "backend/tests/security/test_r03_network_transport.py"
            source_content = (ROOT / source_path).read_text(encoding="utf-8")
            literals = [node for node in ast.walk(ast.parse(source_content)) if isinstance(node,ast.Constant) and node.value == value]
            assert literals
            source_line = min(node.lineno for node in literals)
            assert "_install_socket_fixtures" in source_content and "synthetic" in value
            evidence_type = "isolated_socket_exception_red_test_literal"
        elif "native_auth_failure.stdout.log" in relative:
            source_path, source_line = "backend/tests/conftest.py",109
            evidence_type = "generated_credential_redaction_marker"
        elif "forced_failure_showlocals" in relative:
            source_path, source_line = "reports/runs/recovery_r01_search_tls_review_1_20261015/review_checks.py",53
            candidate_commit = "4b4b9763dc0b75594864b3893dc95a215861d594"
            report_path = "reports/reviews/recovery/G-A-R01-search-tls-review-1.md"
            evidence_type = "generated_credential_redaction_marker"
        elif "credential_failure_v2_sanitized.log" in relative:
            source_path,source_line = "reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_probe_v2.py",34
            candidate_commit = "0fe642b1c9e5fe4dafa2774e9432bd96079c1b72"
            report_path = "reports/reviews/recovery/G-A-R02-persistence-review-1.md"
            evidence_type = "generated_credential_redaction_marker"
        elif "credential_failure_sanitized.log" in relative:
            source_path,source_line = "reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_probe.py",37
            candidate_commit = "0fe642b1c9e5fe4dafa2774e9432bd96079c1b72"
            report_path = "reports/reviews/recovery/G-A-R02-persistence-review-1.md"
            evidence_type = "generated_credential_redaction_marker"
        elif "review_header_" in relative:
            report_path = "reports/reviews/recovery/G-A-R03-network-review-1-recheck-2.md" if "recheck_2" in relative else "reports/reviews/recovery/G-A-R03-network-review-1-recheck.md"
            candidate_commit = "2522b3a941030f373ccd1736bd54cee411e939a9" if "recheck_2" in relative else "59466ceb1703e2741406939adcfb1196e20c77d2"
            assert "仅合成" in content and "SocketFixture" in content and "fixture_only" in content
            evidence_type = "isolated_socket_review_literal"
        elif "independent_negative.spec.ts" in relative:
            candidate_commit = "a0a94f1007dfdb1811df327ca2f931034af33a2e"
            report_path = "reports/reviews/recovery/G-B-R05-question-frontend-review-1.md"
            assert "page.route" in content and "route.fulfill" in content
            evidence_type = "isolated_playwright_fulfilled_csrf_literal"
        else:
            raise AssertionError("unreviewed_path")
        source_content = (ROOT / source_path).read_text(encoding="utf-8")
        assert value in source_content.splitlines()[source_line-1]
        source_snapshot = snapshots.setdefault(source_path,snapshot(source_path))
        origin = {"source_path":source_path,"source_line":source_line,"source_sha256":source_snapshot["sha256"],"data_mode":"fixture","evidence_type":evidence_type}
        if report_path:
            review_snapshot = snapshots.setdefault(report_path,snapshot(report_path))
            origin.update(source_type="review_fixture",review_candidate_commit=candidate_commit,review_report_path=report_path,review_report_sha256=review_snapshot["sha256"],source_content_git_blob=source_snapshot["blob_sha"])
        else:
            origin.update(source_type="git",source_commit=head,source_blob=git_output("rev-parse",f"{head}:{source_path}"))
        pattern = security_scan.PATTERNS[item["pattern_id"]]
        record = {"path":relative,"raw_sha256":item["raw_sha256"],"pattern_id":item["pattern_id"],"pattern_version":1,"pattern_sha256":hashlib.sha256(pattern.pattern.encode()).hexdigest(),"start":item["start"],"end":item["end"],"match_value":value,"category":"verified_synthetic_fixture","fixture_origin":origin,"review_ref":"reports/reviews/recovery/G-B-secret-fixture-classification.md"}
        security_scan._record_from_json(ROOT,record)
        records.append(record)
    assert len(records) == 15
    proposal = {"schema_version":1,"recorded_at":datetime.now(timezone.utc).isoformat(),"source_snapshot_head":head,"span_units":"unicode_codepoints_utf8_errors_ignore_universal_newlines_start_inclusive_end_exclusive","scope":"Exact manually verified isolated test literals and generated redaction markers only. Not actual secret comparison or stage acceptance.","records":records}
    proposal_path = ROOT / "reports/security/gb_fixture_classification_proposal.json"
    proposal_path.write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    loaded = security_scan.load_fixture_classifications(ROOT,proposal_path)
    assert len(loaded) == 15
    (RUN / "proposal_source_snapshots.json").write_text(json.dumps({"recorded_at":datetime.now(timezone.utc).isoformat(),"head":head,"files":list(snapshots.values())},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    original = json.loads((ROOT / "reports/security/recovery_fixture_false_positives.json").read_text(encoding="utf-8"))
    combined = dict(original)
    combined["records"] = [*original["records"],*records]
    combined_path = RUN / "combined_fixture_manifest.json"
    combined_path.write_text(json.dumps(combined,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    assert len(security_scan.load_fixture_classifications(ROOT,combined_path)) == 51
    print(json.dumps({"head":head,"proposal_count":len(records),"combined_count":len(combined["records"]),"record_contract":"passed","occurrence_hash_offset_literal_validation":"passed","source_literal_validation":"passed","shared_manifest_sha256":hashlib.sha256((ROOT / "reports/security/recovery_fixture_false_positives.json").read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
