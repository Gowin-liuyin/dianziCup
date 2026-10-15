"""主控只合并逐值逐位置已核验记录，原记录与扫描规则完整保留。"""

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
receipt = run / "exact_fixture_merge.json"
assert not receipt.exists()
path = root / "reports/security/recovery_fixture_false_positives.json"
original_bytes = path.read_bytes()
assert hashlib.sha256(original_bytes).hexdigest() == "ab87ee5b9f7b9d8b5dc227a789644326659510049dbf7dd2e705a03646d839ac"


def strict_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


original = json.loads(original_bytes, object_pairs_hook=strict_pairs)
proposal = json.loads((root / "reports/security/gb_fixture_classification_proposal.json").read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
records = proposal["records"]
assert len(original["records"]) == 36 and len(records) == 15
assert len({item["path"] for item in records}) == 11
for record in records:
    target = root / record["path"]
    assert target.resolve().is_relative_to(root) and target.is_file()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record["raw_sha256"]
    source = root / record["fixture_origin"]["source_path"]
    assert source.resolve().is_relative_to(root) and source.is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record["fixture_origin"]["source_sha256"]
    assert record["category"] == "verified_synthetic_fixture"
    assert record["review_ref"] == "reports/reviews/recovery/G-B-secret-fixture-classification.md"
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
merged = copy.deepcopy(original)
merged["records"].extend(records)
merged["recorded_at"] = now
merged.setdefault("history", []).append({"recorded_at": now, "prior_recorded_at": original["recorded_at"], "prior_sha256": hashlib.sha256(original_bytes).hexdigest(), "prior_records": 36, "added_records": 15, "added_unique_paths": 11, "review_ref": "reports/reviews/recovery/G-B-secret-fixture-classification.md", "scope": "exact source-bound fixture literals/redaction markers only; rules and scan roots unchanged"})
assert merged["records"][:36] == original["records"]
path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
receipt.write_text(json.dumps({"recorded_at": now, "prior_sha256": hashlib.sha256(original_bytes).hexdigest(), "new_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "records": 51, "existing_records_preserved": True, "scanner_or_ignored_paths_changed": False}, indent=2), encoding="utf-8")
print(receipt.read_text(encoding="utf-8"))
