"""核对已提供的夹具出处，只生成精确分类记录，不修改或复制原始日志。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.security_scan import PATTERNS


def main() -> None:
    source_directory = REPOSITORY_ROOT / "reports/runs/recovery_r01_frontend_20261014"
    inventory = json.loads((source_directory / "synthetic_occurrences.json").read_text())
    records = []
    for file_record in inventory["files"]:
        relative_path = "reports/runs/recovery_r01_frontend_20261014/" + Path(file_record["path"]).name
        raw_content = (REPOSITORY_ROOT / relative_path).read_bytes()
        raw_sha256 = hashlib.sha256(raw_content).hexdigest()
        assert raw_sha256 == file_record["sha256"]
        content = raw_content.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
        matched_records = []
        for pattern_id, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                line = content[:match.start()].count("\n") + 1
                origin_record = next(record for record in file_record["occurrences"]
                                     if record["line"] == line and record["pattern"] == pattern_id)
                origin = origin_record["origins"][0]
                original_source = subprocess.check_output(
                    ["git", "show", origin["source_commit"] + ":" + origin["source_path"]],
                    cwd=REPOSITORY_ROOT,
                )
                assert hashlib.sha256(original_source).hexdigest() == origin["source_sha256"]
                original_blob = subprocess.check_output(
                    ["git", "rev-parse", origin["source_commit"] + ":" + origin["source_path"]],
                    cwd=REPOSITORY_ROOT,
                ).decode().strip()
                assert original_blob == origin["source_blob"]
                fixture_value = origin_record["synthetic_name"]
                assert fixture_value in original_source.decode().splitlines()[origin["source_line"] - 1]
                matched_records.append({
                    "path": relative_path, "raw_sha256": raw_sha256,
                    "pattern_id": pattern_id, "pattern_version": 1,
                    "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(),
                    "start": match.start(), "end": match.end(), "match_value": fixture_value,
                    "category": "verified_synthetic_fixture", "fixture_origin": origin,
                    "review_ref": "reports/reviews/recovery/G-A-R01-behavior-review-1.md#必须修复",
                })
        assert len(matched_records) == len(file_record["occurrences"])
        records.extend(matched_records)
    review_relative_path = "reports/runs/recovery_r01_behavior_review_1_20261014/backend_security.log"
    review_raw = (Path("D:/dianzi") / review_relative_path).read_bytes()
    review_sha256 = hashlib.sha256(review_raw).hexdigest()
    assert review_sha256 == "80205b50cd48993b5c27930ce2fe06930c69a49b910bccf9008cc19afe338c98"
    review_content = review_raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    fixture_origin = next(record["fixture_origin"] for record in records
                          if record["match_value"] == "fixture-csrf")
    for pattern_id, pattern in PATTERNS.items():
        for match in pattern.finditer(review_content):
            assert match.group(2) == "fixture-csrf"
            records.append({
                "path": review_relative_path, "raw_sha256": review_sha256,
                "pattern_id": pattern_id, "pattern_version": 1,
                "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(),
                "start": match.start(), "end": match.end(), "match_value": "fixture-csrf",
                "category": "verified_synthetic_fixture", "fixture_origin": fixture_origin,
                "review_ref": "reports/reviews/recovery/G-A-R01-behavior-review-1.md#必须修复",
            })
    review_fixture_path = "reports/runs/recovery_r01_behavior_review_1_20261014/frontend_behavior.test.tsx"
    review_fixture_raw = (Path("D:/dianzi") / review_fixture_path).read_bytes()
    review_fixture_hash = hashlib.sha256(review_fixture_raw).hexdigest()
    assert review_fixture_hash == "9b401b2a37da5375326f82a838186f43973b230b12cb5247964757eec953661c"
    review_fixture_content = review_fixture_raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    assert "vi.stubGlobal('fetch'" in review_fixture_content
    assert "data_mode: 'fixture'" in review_fixture_content
    report_path = "reports/reviews/recovery/G-A-R01-behavior-review-1.md"
    review_report_sha256 = hashlib.sha256((Path("D:/dianzi") / report_path).read_bytes()).hexdigest()
    assert review_report_sha256 == "30b9fa7ccd8496537aafe4f79eff5dea1d7d1840482a3b435c788e4a69cf580a"
    for pattern_id, pattern in PATTERNS.items():
        for match in pattern.finditer(review_fixture_content):
            matched_text = match.group(0)
            quote_start = min(index for index, character in enumerate(matched_text) if character in "\"'")
            fixture_value = matched_text[quote_start + 1:-1]
            assert fixture_value in {"synthetic-csrf-a", "synthetic-csrf-b"}
            records.append({
                "path": review_fixture_path, "raw_sha256": review_fixture_hash,
                "pattern_id": pattern_id, "pattern_version": 1,
                "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(),
                "start": match.start(), "end": match.end(), "match_value": fixture_value,
                "category": "verified_synthetic_fixture",
                "fixture_origin": {
                    "source_type": "review_fixture", "source_path": review_fixture_path,
                    "source_sha256": review_fixture_hash,
                    "source_line": review_fixture_content[:match.start()].count("\n") + 1,
                    "data_mode": "fixture", "review_report_path": report_path,
                    "review_report_sha256": review_report_sha256,
                    "review_candidate_commit": "4a17ca7b967a10d6077ba5219984a2d1a74cf320",
                },
                "review_ref": report_path + "#必须修复",
            })
    recheck_path = "reports/runs/recovery_r01_behavior_review_1_recheck_20261015/backend_security.log"
    recheck_raw = (Path("D:/dianzi") / recheck_path).read_bytes()
    recheck_sha256 = hashlib.sha256(recheck_raw).hexdigest()
    assert recheck_sha256 == "c22e0f225db93c9d4aca09f578f220e81d9aa47ca6dff8d578ca98596028081a"
    recheck_content = recheck_raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    memory_origin = next(record["fixture_origin"] for record in records
                         if record["match_value"] == "fixture-memory-csrf")
    for pattern_id, pattern in PATTERNS.items():
        for match in pattern.finditer(recheck_content):
            assert "fixture-memory-csrf" in match.group(0)
            records.append({
                "path": recheck_path, "raw_sha256": recheck_sha256,
                "pattern_id": pattern_id, "pattern_version": 1,
                "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(),
                "start": match.start(), "end": match.end(), "match_value": "fixture-memory-csrf",
                "category": "verified_synthetic_fixture", "fixture_origin": memory_origin,
                "review_ref": report_path + "#必须修复",
            })
    original_test_path = "backend/tests/security/test_t06_authentication_and_scope.py"
    fixed_input = "fd4f1d42e1ad2e39ff7c80897fd50511c3faf299"
    original_test_raw = subprocess.check_output(["git", "show", fixed_input + ":" + original_test_path], cwd=REPOSITORY_ROOT)
    original_test_blob = subprocess.check_output(["git", "rev-parse", fixed_input + ":" + original_test_path], cwd=REPOSITORY_ROOT).decode().strip()
    original_test_lines = original_test_raw.decode("utf-8").splitlines()
    for relative_path in ["reports/runs/recovery_r01_secret_classification_20261015/diff_check.log",
                          "reports/runs/recovery_r01_secret_classification_20261015/diff_check_final.log"]:
        raw_content = (REPOSITORY_ROOT / relative_path).read_bytes()
        content = raw_content.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
        for pattern_id, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                matched_text = match.group(0)
                quote_start = min(index for index, character in enumerate(matched_text) if character in "\"'")
                fixture_value = matched_text[quote_start + 1:-1]
                assert fixture_value in {"password authentication failed", "synthetic-credential"}
                printed_line = content.splitlines()[content[:match.start()].count("\n")].lstrip("+").strip()
                source_line = next(line_number for line_number, line in enumerate(original_test_lines, 1)
                                   if line.strip() == printed_line)
                assert fixture_value in original_test_lines[source_line - 1]
                records.append({
                    "path": relative_path, "raw_sha256": hashlib.sha256(raw_content).hexdigest(),
                    "pattern_id": pattern_id, "pattern_version": 1,
                    "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(),
                    "start": match.start(), "end": match.end(), "match_value": fixture_value,
                    "category": "verified_synthetic_fixture",
                    "fixture_origin": {
                        "source_commit": fixed_input, "source_blob": original_test_blob,
                        "source_path": original_test_path, "source_line": source_line,
                        "source_sha256": hashlib.sha256(original_test_raw).hexdigest(),
                        "data_mode": "fixture",
                        "fixture_case": "test_secret_scan_distinguishes_public_failure_check_from_credential_literal",
                    },
                    "review_ref": report_path + "#必须修复",
                })
    table = {
        "schema_version": 1,
        "recorded_at": datetime.now().astimezone().isoformat(),
        "span_units": "unicode_codepoints_utf8_errors_ignore_universal_newlines_start_inclusive_end_exclusive",
        "scope": "Exact reviewed synthetic occurrences only; all other matches fail.",
        "records": records,
    }
    table_path = REPOSITORY_ROOT / "reports/security/recovery_fixture_false_positives.json"
    table_path.write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": len(records), "file_counts": dict(Counter(record["path"] for record in records)),
                      "table_sha256": hashlib.sha256(table_path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
