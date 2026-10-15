"""Verify historical synthetic provenance, not a production scanner or exemption."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-recheck\dianzi")
artifact = Path(__file__).parent
manifest = json.loads((candidate / "reports/runs/recovery_r01_frontend_20261014/synthetic_occurrences.json").read_text(encoding="utf-8-sig"))
patterns = {
    "original_secret_pattern": re.compile(r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", re.IGNORECASE),
    "original_secret_value_pattern": re.compile(r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|password|passwd|token|jwt)\s*[:=]\s*['\"]([^'\"]{6,})['\"]", re.IGNORECASE),
}
known_synthetic = {"fixture-csrf", "fixture-memory-csrf"}
report = {"mode": "readonly historical byte/provenance verification; no classifier implementation", "patterns_sha256": {name: hashlib.sha256(pattern.pattern.encode()).hexdigest() for name, pattern in patterns.items()}, "files": [], "sources": [], "review_log": {}}
source_keys = set()
for entry in manifest["files"]:
    filename = Path(entry["path"].replace("\\", "/")).name
    relative = "reports/runs/recovery_r01_frontend_20261014/" + filename
    raw = (candidate / relative).read_bytes()
    content = raw.decode("utf-8", errors="ignore")
    matches = []
    for name, pattern in patterns.items():
        for match in pattern.finditer(content):
            value = match.group(2) if name.endswith("value_pattern") else re.search(r"['\"]([^'\"]+)['\"]$", match.group()).group(1)
            line = content[:match.start()].count("\n") + 1
            matches.append({"pattern": name, "line": line, "start_codepoint": match.start(), "end_codepoint": match.end(), "synthetic_name": value if value in known_synthetic else "[not established synthetic]", "match_sha256": hashlib.sha256(match.group().encode()).hexdigest(), "known_synthetic": value in known_synthetic})
    declared = sorted((item["pattern"], item["line"], item["synthetic_name"]) for item in entry["occurrences"])
    observed = sorted((item["pattern"], item["line"], item["synthetic_name"]) for item in matches)
    record = {"path": relative, "expected_sha256": entry["sha256"], "actual_sha256": hashlib.sha256(raw).hexdigest(), "hash_matches": hashlib.sha256(raw).hexdigest() == entry["sha256"], "declared_matches": len(declared), "observed_matches": len(matches), "occurrence_table_matches": declared == observed, "matches": matches}
    report["files"].append(record)
    for occurrence in entry["occurrences"]:
        for origin in occurrence["origins"]:
            source_keys.add((origin["source_commit"], origin["source_path"], origin["source_blob"], origin["source_sha256"]))
for commit, relative, expected_blob, expected_hash in sorted(source_keys):
    source_bytes = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=candidate, capture_output=True, check=True).stdout
    source_blob = subprocess.run(["git", "rev-parse", f"{commit}:{relative}"], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip()
    source_text = source_bytes.decode("utf-8")
    report["sources"].append({"source_commit": commit, "source_path": relative, "expected_blob": expected_blob, "actual_blob": source_blob, "blob_matches": source_blob == expected_blob, "expected_sha256": expected_hash, "git_blob_content_sha256": hashlib.sha256(source_bytes).hexdigest(), "sha256_matches": hashlib.sha256(source_bytes).hexdigest() == expected_hash, "synthetic_names_present": sorted(value for value in known_synthetic if value in source_text), "fictional_fetch_boundary_present": 'vi.stubGlobal("fetch"' in source_text or "mockResponse" in source_text})
historical_review_log = Path(r"D:\dianzi\reports\runs\recovery_r01_behavior_review_1_20261014\backend_security.log")
raw = historical_review_log.read_bytes()
content = raw.decode("utf-8", errors="ignore")
matches = []
for name, pattern in patterns.items():
    for match in pattern.finditer(content):
        value = match.group(2) if name.endswith("value_pattern") else re.search(r"['\"]([^'\"]+)['\"]$", match.group()).group(1)
        matches.append({"pattern": name, "line": content[:match.start()].count("\n") + 1, "start_codepoint": match.start(), "end_codepoint": match.end(), "synthetic_name": value if value in known_synthetic else "[not established synthetic]", "known_synthetic": value in known_synthetic})
report["review_log"] = {"path": "reports/runs/recovery_r01_behavior_review_1_20261014/backend_security.log", "sha256": hashlib.sha256(raw).hexdigest(), "matches": matches, "known_fixture_source": "4a17ca7:frontend/src/api/client.test.ts:45; traceback reports the literal synthetic mockResponse nonce", "contains_original_failure": "1 failed, 27 passed" in content, "is_in_new_candidate": (candidate / "reports/runs/recovery_r01_behavior_review_1_20261014/backend_security.log").exists()}
report["summary"] = {"candidate_historical_files": len(report["files"]), "candidate_matches": sum(item["observed_matches"] for item in report["files"]), "physical_lines": len({(item["path"], match["line"]) for item in report["files"] for match in item["matches"]}), "all_file_hashes_match": all(item["hash_matches"] for item in report["files"]), "all_occurrence_tables_match": all(item["occurrence_table_matches"] for item in report["files"]), "all_source_blobs_match": all(item["blob_matches"] for item in report["sources"]), "review_log_matches": len(matches), "review_log_known_synthetic_matches": sum(item["known_synthetic"] for item in matches), "classification_tamper_and_new_credential_rejection_tests": "not_run: classifier not in this candidate; proposal only", "authorized_secret_exact_scan": "not_run by reviewer: no secret values accessed"}
(artifact / "classification_evidence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report["summary"], ensure_ascii=False))
print(json.dumps({"candidate_files": [{key: item[key] for key in ("path", "actual_sha256", "hash_matches", "observed_matches", "occurrence_table_matches")} for item in report["files"]], "review_log_sha256": report["review_log"]["sha256"], "source_sha256_match_flags": [item["sha256_matches"] for item in report["sources"]]}, ensure_ascii=False))
assert report["summary"]["all_file_hashes_match"]
assert report["summary"]["all_occurrence_tables_match"]
assert report["summary"]["all_source_blobs_match"]
