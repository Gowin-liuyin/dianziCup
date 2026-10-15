"""Replay reviewer-owned public synthetic inputs without changing their probes or artifacts."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FIXTURES = Path("C:/Users/yinha/AppData/Local/Temp/r19-review-only-synthetic-9d7uhd1i")
ZONE = timezone(timedelta(hours=8))
PREFIX = sys.argv[1]
records = []


def execute(name: str, arguments: list[str], expected: int = 2) -> None:
    argv = [sys.executable, str(ROOT / "scripts/annotation/prepare.py"), *arguments]
    start = datetime.now(ZONE).isoformat(timespec="seconds")
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False, timeout=30)
    records.append({"name": name, "argv": argv, "cwd": str(ROOT), "start": start, "end": datetime.now(ZONE).isoformat(timespec="seconds"), "exit_code": result.returncode, "expected_exit": expected, "expectation_met": result.returncode == expected, "stdout": result.stdout, "stderr": result.stderr})


with tempfile.TemporaryDirectory(prefix="r19-author-fix1-synthetic-only-") as temporary:
    outside = Path(temporary).resolve()
    case_file = str(FIXTURES / "base_synthetic.json")
    alias_file = str(FIXTURES / "alias_refers_other_family_cross_split.json")
    orphan_file = str(FIXTURES / "orphan_adjudication.json")
    execute("alias_primary_validate", ["validate", "--input", alias_file])
    execute("alias_primary_export", ["export", "--input", alias_file, "--output", str(outside / "alias_export.json")])
    execute("orphan_validate", ["validate", "--input", case_file, "--labels", orphan_file])
    orphan_export = outside / "orphan_export.json"
    execute("orphan_export", ["export", "--input", case_file, "--labels", orphan_file, "--output", str(orphan_export)])
    if orphan_export.exists():
        payload = json.loads(orphan_export.read_text(encoding="utf-8"))
        records[-1]["invalid_adjudication_preserved"] = payload["annotations"]["adjudication"] == json.loads(Path(orphan_file).read_text(encoding="utf-8"))["adjudication"]
        records[-1]["annotation_sha256_added"] = "annotation_sha256" in payload
        records[-1]["export_file_sha256"] = hashlib.sha256(orphan_export.read_bytes()).hexdigest()
        execute("orphan_export_revalidate", ["validate", "--input", str(orphan_export)])
    else:
        execute("orphan_export_revalidate", ["validate", "--input", str(FIXTURES / "orphan_export.json")])
    duplicate = FIXTURES / "orphan_duplicate_adjudications.json"
    execute("orphan_duplicate_validate", ["validate", "--input", case_file, "--labels", str(duplicate)])
    linked = outside / "registered-worktree"
    add = ["git", "worktree", "add", "--detach", "--no-checkout", str(linked), "a0c76800202a9869c4e24918b84893ebcec52a61"]
    subprocess.run(add, cwd=ROOT, capture_output=True, check=True)
    try:
        execute("labels_to_new_registered_worktree", ["export", "--input", case_file, "--labels", str(FIXTURES / "claimed_humans_are_synthetic_only.json"), "--output", str(linked / "synthetic_label_export.json")])
        records[-1]["output_exists"] = (linked / "synthetic_label_export.json").exists()
    finally:
        assert linked.resolve().is_relative_to(outside)
        assert {entry.name for entry in linked.iterdir()}.issubset({".git", "synthetic_label_export.json"})
        subprocess.run(["git", "worktree", "remove", "--force", str(linked)], cwd=ROOT, capture_output=True, check=True)

code_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
output = {"code_sha": code_sha, "explicit_synthetic_inputs": True, "actual_human_labels": 0, "real_holdout_accessed": False, "reviewer_fixture_root": str(FIXTURES), "records": records, "mismatches": [record["name"] for record in records if not record["expectation_met"]]}
with (RUN / f"{PREFIX}_review_reproduction.json").open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(output, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"probes": len(records), "mismatches": output["mismatches"]}))
raise SystemExit(int(bool(output["mismatches"])))
