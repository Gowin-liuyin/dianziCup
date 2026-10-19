"""Separate the append-only backend capture without altering any captured event bytes."""

import hashlib
import json
import subprocess

import review_checks

ROOT, RUN = review_checks.ROOT, review_checks.RUN


def main():
    path = "reports/runs/g_c_batch14_mode_review_1_20261017/pg_backend_creation.jsonl"
    original = subprocess.check_output(["git", "show", "04da910b5217def869d03800a7144967d8d520c6:" + path], cwd=ROOT)
    existing = (ROOT / path).read_bytes()
    assert existing.startswith(original)
    added = existing[len(original):]
    assert added
    records = [json.loads(row) for row in added.splitlines()]
    assert all(row["database"] == "test_dianzi_r06_mode_f47b2a40a8194a" for row in records)
    target = RUN / "recheck_pg_backend_creation.jsonl"
    assert not target.exists()
    target.write_bytes(added)
    (ROOT / path).write_bytes(original)
    result = {"split_at": review_checks.checks.now(), "existing_capture_before_sha256": hashlib.sha256(existing).hexdigest(), "first_capture_sha256": hashlib.sha256(original).hexdigest(), "recheck_capture_sha256": hashlib.sha256(added).hexdigest(), "first_capture_byte_identical_to_04da": (ROOT / path).read_bytes() == original, "all_recheck_records_have_owned_nonce_database": True, "recheck_backend_creation_records": len(records), "no_record_bytes_changed": original + target.read_bytes() == existing}
    (RUN / "backend_journal_split.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
