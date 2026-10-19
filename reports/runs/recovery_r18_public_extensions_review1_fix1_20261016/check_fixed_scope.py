"""Record the exact schema fix, unchanged prior probes, and frozen artifact digests."""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE = "831c61f5c82d663434172a258bbd0c85757a6567"
OLD_CODE = "456320b6c78e2936fd9f9767724ec3eb17f5c88b"


def blob(revision: str, relative_path: str) -> bytes:
    result = subprocess.run(["git", "show", revision + ":" + relative_path], cwd=ROOT,
                            capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("Cannot read fixed Git blob")
    return result.stdout


schema_path = "contracts/schemas/public_api_extensions_v1.json"
current_bytes = blob(CODE, schema_path)
current = json.loads(current_bytes)
before = json.loads(blob(OLD_CODE, schema_path))
legacy = json.loads(blob(CODE, "contracts/schemas/public_api_v2.json"))
Draft202012Validator.check_schema(current)
pattern = current["$defs"]["TaskDescriptor"]["properties"]["poll_uri"]["pattern"]
before["$defs"]["TaskDescriptor"]["properties"]["poll_uri"]["pattern"] = pattern
original_probe = Path("D:/dianzi/reports/runs/recovery_r18_public_extensions_review1_20261016/test_independent_contract.py")
original_probe_bytes = original_probe.read_bytes()
copied_probe_bytes = (RUN / "test_independent_contract.py").read_bytes()
original_probe_manifest = json.loads(Path(
    "D:/dianzi/reports/runs/recovery_r18_public_extensions_review1_20261016/manifest.json"
).read_text(encoding="utf-8"))
recorded_probe_sha = next(
    item["sha256"] for item in original_probe_manifest["files"]
    if item["path"].endswith("/test_independent_contract.py")
)
receipt = {
    "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "code_sha": CODE,
    "schema_git_blob_sha256": hashlib.sha256(current_bytes).hexdigest(),
    "schema_checkout_sha256": hashlib.sha256((ROOT / schema_path).read_bytes()).hexdigest(),
    "schema_checkout_lf_sha256": hashlib.sha256((ROOT / schema_path).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    "only_structural_schema_change_is_new_poll_uri_pattern": current == before,
    "current_poll_uri_pattern": pattern,
    "legacy_14_defs_structurally_equal": all(current["$defs"][name] == definition for name, definition in legacy["$defs"].items()),
    "legacy_v2_blob_unchanged": blob(CODE, "contracts/schemas/public_api_v2.json") == blob(OLD_CODE, "contracts/schemas/public_api_v2.json"),
    "prior23_test_blob_unchanged": blob(CODE, "backend/tests/contract/test_r18_public_extensions.py") == blob(OLD_CODE, "backend/tests/contract/test_r18_public_extensions.py"),
    "prior97_test_byte_identical": copied_probe_bytes == original_probe_bytes,
    "prior97_recorded_sha_matches": hashlib.sha256(copied_probe_bytes).hexdigest() == recorded_probe_sha,
    "prior97_sha256": hashlib.sha256(copied_probe_bytes).hexdigest(),
    "prior97_original_manifest_sha256": hashlib.sha256(Path(
        "D:/dianzi/reports/runs/recovery_r18_public_extensions_review1_20261016/manifest.json"
    ).read_bytes()).hexdigest(),
    "json_schema_meta_validation": "passed", "physical_pg_requests": 0, "paid_calls": 0,
    "only_code_recheck_not_runtime_or_document_updates": True,
}
assert all(receipt[key] for key in (
    "only_structural_schema_change_is_new_poll_uri_pattern", "legacy_14_defs_structurally_equal",
    "legacy_v2_blob_unchanged", "prior23_test_blob_unchanged", "prior97_test_byte_identical", "prior97_recorded_sha_matches",
))
(RUN / "fixed_scope.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
