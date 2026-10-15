"""按独立审查发现固定夹具的精确字节，避免新检出改变已审内容哈希。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
receipt_path = run / "classified_fixture_bytes_freeze.json"
assert not receipt_path.exists()
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
table_path = root / "reports/security/recovery_fixture_false_positives.json"
table_before = table_path.read_bytes()
table = json.loads(table_before)
paths = sorted({row["path"] for row in table["records"]})
rows = []
attributes = root / ".gitattributes"
attribute_text = attributes.read_text(encoding="utf-8")
for relative_path in paths:
    expected = {row["raw_sha256"] for row in table["records"] if row["path"] == relative_path}
    payload = (root / relative_path).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    assert expected == {digest}, relative_path
    old_blob = subprocess.check_output(["git", "show", "HEAD:" + relative_path], cwd=root)
    rows.append({"path": relative_path, "reviewed_raw_sha256": digest, "prior_git_blob_sha256": hashlib.sha256(old_blob).hexdigest(), "raw_bytes": len(payload), "line_endings_only_from_prior_blob": payload.replace(b"\r\n", b"\n") == old_blob.replace(b"\r\n", b"\n")})
    diff_attribute = " -diff" if relative_path.startswith("reports/") else ""
    line = relative_path + " -text" + diff_attribute + " whitespace=trailing-space,space-before-tab,cr-at-eol\n"
    if line not in attribute_text:
        attribute_text += line
attributes.write_text(attribute_text, encoding="utf-8")
subprocess.run(["git", "add", "--", ".gitattributes"], cwd=root, check=True, capture_output=True)
subprocess.run(["git", "add", "--renormalize", "--", *paths], cwd=root, check=True, capture_output=True)
for row in rows:
    blob = subprocess.check_output(["git", "show", ":" + row["path"]], cwd=root)
    assert hashlib.sha256(blob).hexdigest() == row["reviewed_raw_sha256"], row["path"]
assert table_before == table_path.read_bytes()
semantic_diff = subprocess.check_output(["git", "diff", "--cached", "--ignore-space-at-eol", "--", "backend/src", "frontend/src"], cwd=root)
assert not semantic_diff
check = subprocess.run(["git", "diff", "--cached", "--check"], cwd=root, capture_output=True)
record = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "cause": "Git core.autocrlf=true changed exact reviewed fixture bytes in a clean checkout; some historical blobs had LF while reviewed worktree artifacts had CRLF", "records": len(table["records"]), "paths": rows, "manifest_bytes_unchanged": True, "scanner_patterns_spans_values_ignores_unchanged": True, "semantic_src_diff_bytes_ignoring_line_endings": len(semantic_diff), "diff_check_exit_code": check.returncode, "scope": "Exact classified file paths only; no generalized credential exception. Existing historical fixture_origin source_sha256 is observed worktree bytes, while source_blob identifies Git-normalized bytes; these are distinct provenance identifiers."}
assert check.returncode == 0
receipt_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
subprocess.run(["git", "add", "--", receipt_path.relative_to(root).as_posix(), Path(__file__).relative_to(root).as_posix(), "reports/runs/recovery_r05_controller_20261015/fixture_git_blob_probe.json"], cwd=root, check=True, capture_output=True)
print(json.dumps({"recorded_at": record["ended_at"], "records": len(table["records"]), "files": len(paths), "manifest_unchanged": True, "semantic_src_diff_bytes": len(semantic_diff), "diff_check_exit_code": check.returncode}))
