"""Record immutable source checks and distinguish semantic holes from shape checks."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone, timedelta

from jsonschema import Draft202012Validator


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE = "456320b6c78e2936fd9f9767724ec3eb17f5c88b"
checks: dict[str, object] = {"checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "code_sha": CODE}
extension = ROOT / "contracts/schemas/public_api_extensions_v1.json"
legacy = ROOT / "contracts/schemas/public_api_v2.json"
schemas = [json.loads(path.read_text(encoding="utf-8")) for path in (extension, legacy)]
for schema in schemas:
    Draft202012Validator.check_schema(schema)
checks["json_schema_meta_validation"] = "passed"
checks["extension_raw_sha256"] = hashlib.sha256(extension.read_bytes()).hexdigest()
checks["legacy_raw_sha256"] = hashlib.sha256(legacy.read_bytes()).hexdigest()
checks["legacy_canonical_sha256"] = hashlib.sha256(json.dumps(
    schemas[1], ensure_ascii=False, sort_keys=True, separators=(",", ":")
).encode("utf-8")).hexdigest()
checks["legacy_defs_count"] = len(schemas[1]["$defs"])
checks["extension_defs_count"] = len(schemas[0]["$defs"])
checks["legacy_definitions_structurally_identical"] = all(
    schemas[0]["$defs"][name] == definition for name, definition in schemas[1]["$defs"].items()
)
base = subprocess.run(["git", "show", CODE + "^:contracts/schemas/public_api_v2.json"], cwd=ROOT,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
checks["parent_v2_git_blob_exit"] = base.returncode
checks["legacy_parent_blob_sha256"] = hashlib.sha256(base.stdout).hexdigest()
checks["legacy_parent_content_equal_with_checkout_newline_normalization"] = (
    base.stdout.replace(b"\r\n", b"\n") == legacy.read_bytes().replace(b"\r\n", b"\n")
)
extension_blob = subprocess.run(["git", "show", CODE + ":contracts/schemas/public_api_extensions_v1.json"],
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
checks["extension_git_blob_sha256"] = hashlib.sha256(extension_blob.stdout).hexdigest()
checks["extension_checkout_lf_sha256"] = hashlib.sha256(extension.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
checks["extension_git_blob_read_exit"] = extension_blob.returncode
cache = Path("D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790")
checks["external_encoding_cache"] = {
    "path": str(cache), "bytes": cache.stat().st_size,
    "sha256": hashlib.sha256(cache.read_bytes()).hexdigest(),
    "read_only": True, "download_performed": False,
    "encoding_run_performed": False, "runtime_8000_token_budget_verified": False,
}
raw_inputs = [
    "D:/dianzi/reports/runs/recovery_r18_public_contracts_20261016/commands.json",
    "D:/dianzi/reports/runs/recovery_r18_public_contracts_20261016/whole_coverage_scope_mismatch.stdout.log",
    "D:/dianzi/reports/runs/recovery_r18_public_contracts_20261016/contract_scoped.xml",
    "D:/dianzi/reports/runs/recovery_r18_output_encoding_20261016/encoding_receipt.json",
    "D:/dianzi/reports/runs/recovery_r18_output_encoding_20261016/encoding_receipt_initial.json",
    "D:/dianzi/reports/runs/recovery_r18_output_encoding_20261016/offline_encoding_smoke_initial.log",
    "D:/dianzi/reports/runs/recovery_r18_output_encoding_20261016/offline_encoding_smoke.log",
    "D:/dianzi/reports/runs/recovery_r18_output_encoding_20261016/official_installed_o200k_source.txt",
]
checks["non_frozen_root_raw_inputs"] = []
for value in raw_inputs:
    path = Path(value)
    content = path.read_bytes()
    record = {"path": value, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
              "frozen_git_source": False}
    if path.suffix == ".json":
        record["content"] = json.loads(content)
    elif path.suffix == ".log":
        record["content"] = content.decode("utf-8", errors="replace")
    checks["non_frozen_root_raw_inputs"].append(record)
spec = importlib.util.spec_from_file_location("review_synthetic_shapes", RUN / "test_independent_contract.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
observations = []


def observe(name: str, definition: str, sample: object, deployment_requirement: str) -> None:
    observations.append({"name": name, "definition": definition, "input": sample,
                         "schema_accepts": module.valid(definition, sample),
                         "required_before_public_runtime": deployment_requirement})


grade = module.finding()
grade["citations"][0]["source_uri"] = "javascript:alert(1)"
observe("inherited_uri_format_is_not_safe_link_policy", "RiskFinding", grade,
        "Producer and typed client must apply safe public citation URI policy; preserved v2 URI syntax alone cannot do this.")
health = module.source()
health.update(last_attempt_at=None, last_success_at=None)
observe("healthy_with_no_observation_dates", "SourceDescriptor", health,
        "Producer must derive actual persistent observation; missing observations cannot produce healthy.")
no_risk = module.summary()
no_risk.update(confirmation="none_confirmed", unknown_component_indices=[0])
observe("contradictory_summary_cross_array", "RiskSummary", no_risk,
        "Reject high finding plus none_confirmed, and complete coverage plus unresolved index, in producer/typed validator.")
out_of_range = module.summary()
out_of_range["findings"][0]["component_index"] = 199
observe("finding_not_in_single_component_request", "RiskSummary", out_of_range,
        "Bind indices to actual request, not the absolute max of 200.")
different_id = module.task()
different_id["poll_uri"] = "/api/v1/tasks/99999999-2222-4333-8444-555555555555"
observe("poll_id_differs_from_task_id", "TaskDescriptor", different_id,
        "Typed validator must compare parsed poll UUID with task_id; PG producer must use actual job state.")
partial = module.envelope("partial")
partial.update(result=None, error=None, completed_steps=[], pending_steps=[], failed_steps=[])
observe("partial_has_no_runtime_progress_fact", "TaskResultEnvelope", partial,
        "Producer must expose actual partial facts/steps; schema acceptance alone cannot prove terminal completion or successful execution.")
checks["semantic_observations_not_business_acceptance_tests"] = observations
checks["physical_pg_requests"] = 0
checks["paid_calls"] = 0
(RUN / "provenance.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in checks.items() if key not in {
    "non_frozen_root_raw_inputs", "semantic_observations_not_business_acceptance_tests"
}}, ensure_ascii=False, indent=2))
print("semantic_observations", [(item["name"], item["schema_accepts"]) for item in observations])
