"""Independently verify every approved byte/span and its fixed source evidence."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-recheck-final\dianzi")
sys.path.insert(0, str(candidate))
from scripts import security_scan

artifact = Path(__file__).parent
main_workspace = Path(r"D:\dianzi")


def evidence_path(relative_path):
    in_candidate = candidate / relative_path
    if in_candidate.is_file():
        return in_candidate, "candidate"
    in_main = main_workspace / relative_path
    if in_main.is_file():
        return in_main, "main_workspace_retained_evidence"
    raise FileNotFoundError(relative_path)


table_path = candidate / "reports/security/recovery_fixture_false_positives.json"
table = json.loads(table_path.read_text(encoding="utf-8"))
loaded = security_scan.load_fixture_classifications(candidate, table_path)
records = []
for row in table["records"]:
    target_path, target_location = evidence_path(row["path"])
    raw = target_path.read_bytes()
    content = raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    found = [match for match in security_scan.PATTERNS[row["pattern_id"]].finditer(content) if match.start() == row["start"] and match.end() == row["end"]]
    value_matches = False
    if len(found) == 1:
        text = found[0].group()
        quote_start = min(index for index, character in enumerate(text) if character in "\"'")
        value_matches = text[quote_start + 1 : -1] == row["match_value"]
    origin = row["fixture_origin"]
    if origin.get("source_type", "git") == "git":
        source_bytes = subprocess.run(["git", "show", f"{origin['source_commit']}:{origin['source_path']}"], cwd=candidate, check=True, capture_output=True).stdout
        blob = subprocess.run(["git", "rev-parse", f"{origin['source_commit']}:{origin['source_path']}"], cwd=candidate, check=True, capture_output=True, text=True).stdout.strip()
        source_identity = blob == origin["source_blob"]
        report_identity = True
    else:
        source_path, source_location = evidence_path(origin["source_path"])
        source_bytes = source_path.read_bytes()
        source_identity = True
        report_path, report_location = evidence_path(origin["review_report_path"])
        report_bytes = report_path.read_bytes()
        report_identity = hashlib.sha256(report_bytes).hexdigest() == origin["review_report_sha256"]
        subprocess.run(["git", "cat-file", "-e", origin["review_candidate_commit"] + "^{commit}"], cwd=candidate, check=True, capture_output=True)
    lines = source_bytes.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    source_line_valid = 1 <= origin["source_line"] <= len(lines)
    records.append({"path": row["path"], "target_location": target_location, "pattern_id": row["pattern_id"], "start": row["start"], "end": row["end"], "raw_hash_matches": hashlib.sha256(raw).hexdigest() == row["raw_sha256"], "span_and_value_match": len(found) == 1 and value_matches, "source_type": origin.get("source_type", "git"), "source_path": origin["source_path"], "source_hash_matches": hashlib.sha256(source_bytes).hexdigest() == origin["source_sha256"], "source_blob_matches": source_identity, "source_line_valid": source_line_valid, "source_line_contains_literal_value": source_line_valid and row["match_value"] in lines[origin["source_line"] - 1], "review_report_hash_matches": report_identity})
summary = {"candidate_sha": "d30eeab1d723080decea5f64a992b909a0d834c2", "table_raw_sha256": hashlib.sha256(table_path.read_bytes()).hexdigest(), "span_units": table["span_units"], "records": len(records), "paths": len({record['path'] for record in records}), "loader_records": len(loaded), "all_raw_hashes": all(record["raw_hash_matches"] for record in records), "all_spans_and_values": all(record["span_and_value_match"] for record in records), "all_source_hashes": all(record["source_hash_matches"] for record in records), "all_source_blobs": all(record["source_blob_matches"] for record in records), "all_source_lines": all(record["source_line_valid"] for record in records), "all_review_report_hashes": all(record["review_report_hash_matches"] for record in records), "literal_source_lines": sum(record["source_line_contains_literal_value"] for record in records)}
(artifact / "classification_provenance.json").write_text(json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
assert all(summary[key] for key in ("all_raw_hashes", "all_spans_and_values", "all_source_hashes", "all_source_blobs", "all_source_lines", "all_review_report_hashes"))
