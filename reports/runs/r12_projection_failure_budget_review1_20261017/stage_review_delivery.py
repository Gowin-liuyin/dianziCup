"""Apply the approved exact Oracle classification and stage only owned lossless review proof."""

import ast
import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
REPORT = ROOT / "reports/reviews/recovery/G-D-R12-projection-failure-budget-review-1.md"
SOURCE = "9cd6381eacc67853c055643d634ffb1812875214"


def git(*arguments):
    result = subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


assert git("rev-parse", "HEAD").decode().strip() == SOURCE
assert not git("diff", "--cached", "--name-only")
oracles = [
    ("backend/tests/unit/test_r01_runtime_settings.py", 45, 50,
     "tests.unit.test_r01_runtime_settings",
     "test_invalid_credential_origins_are_rejected_without_echoing_inputs"),
    ("backend/tests/security/test_r12_retrieval_boundaries.py", 18, 24,
     "tests.security.test_r12_retrieval_boundaries",
     "test_search_client_rejects_untrusted_connection_shapes"),
]
classifications = []
for relative, input_line, function_line, classname, function in oracles:
    frozen = git("show", SOURCE + ":" + relative)
    origin = ast.literal_eval(frozen.decode().splitlines()[input_line - 1].strip().rstrip(","))
    assert isinstance(origin, str)
    for archive in (
        RUN / "related.xml.gz",
        RUN / "author_material_fixed/related_regression_fixed.junit.xml.gz",
    ):
        raw = gzip.decompress(archive.read_bytes())
        matches = [
            case for case in ET.fromstring(raw).findall(".//testcase")
            if case.get("classname") == classname and case.get("name") == function + "[" + origin + "]"
        ]
        assert len(matches) == 1
        classifications.append({
            "archive": archive.relative_to(ROOT).as_posix(),
            "classification": "pattern_finding_retained_synthetic_fixture",
            "classname": classname, "test_function": function,
            "source_path": relative, "source_commit": SOURCE,
            "source_git_blob": git("rev-parse", SOURCE + ":" + relative).decode().strip(),
            "fixture_line": input_line, "function_line": function_line,
            "testcase_bytes_sha256": hashlib.sha256(ET.tostring(matches[0])).hexdigest(),
            "raw_archive_unchanged": True,
        })
boundary = {
    "checked_at": datetime.now(UTC).isoformat(),
    "source_parent": SOURCE,
    "approval": "Root explicitly approved only these two frozen synthetic credential rejection cases",
    "raw_pattern_findings_retained": classifications,
    "other_named_patterns_findings": {name: 0 for name in ("private_key", "openai_key", "postgres_url", "aws_key")},
    "scope": "selected own proof bytes; no full known-secret registry scan or secret environment lookup",
    "scanner_repairs_stopped_after_two_no_stage_progress": True,
    "raw_failure_archives_lossless": True,
    "allowed_report": REPORT.relative_to(ROOT).as_posix(),
    "allowed_run_prefix": RUN.relative_to(ROOT).as_posix() + "/",
}
path = RUN / "commit_boundary_manual.json"
assert not path.exists()
path.write_text(json.dumps(boundary, indent=2) + "\n")
selected = [REPORT]
for folder in (RUN, RUN / "author_material_fixed"):
    for item in sorted(folder.iterdir()):
        suffixes = {".py", ".json", ".gz", ".txt"} if folder == RUN else {".json", ".gz"}
        if item.is_file() and item.suffix in suffixes:
            selected.append(item)
assert all(item == REPORT or item.resolve().is_relative_to(RUN.resolve()) for item in selected)
paths = [item.relative_to(ROOT).as_posix() for item in selected]
spec = RUN / "delivery_staged_paths.nul"
spec.write_bytes(b"\0".join(value.encode() for value in paths) + b"\0")
git("add", "--pathspec-from-file=" + str(spec), "--pathspec-file-nul")
actual = git("diff", "--cached", "--name-only").decode().splitlines()
assert set(actual) == set(paths)
result = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT,
                        capture_output=True, timeout=20)
(RUN / "delivery_staged_diff.raw.log").write_bytes(result.stdout + result.stderr)
assert result.returncode == 0
summary = {
    "staged_count": len(actual), "staged_paths": actual,
    "staged_diff_check_exit_code": result.returncode,
    "outside_owned_scope": [], "classified_oracle_cases": len(oracles),
    "archive_case_matches": len(classifications),
}
(RUN / "delivery_staged_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"staged_count": len(actual), "diff_check_exit": 0, "classified_oracle_cases": 2}))
