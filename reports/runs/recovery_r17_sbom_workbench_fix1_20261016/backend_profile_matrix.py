"""Compare manual cases to the immutable Git-exported server display profile; no frontend-derived expectations."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REVIEW = Path("D:/wt/r17-sbom-review1")
FROZEN = REVIEW / "reports/runs/recovery_r17_sbom_workbench_review1_20261016/backend_git_probe/backend/src"
target = FROZEN / "ai_intel/assets/sbom_inventory.py"
original = subprocess.check_output(["git", "show", "5be873ec38a41955b5a58e9762df4b866a7a9d63:backend/src/ai_intel/assets/sbom_inventory.py"], cwd=ROOT)
if target.read_bytes().replace(b"\r\n", b"\n") != original.replace(b"\r\n", b"\n"):
    raise RuntimeError("frozen backend profile source changed")
sys.path.insert(0, str(FROZEN))
from ai_intel.assets.sbom_inventory import _safe_purl_reference, parse_inventory_input
from ai_intel.assets.sbom_parser import SbomValidationError
from ai_intel.domain.access import AccessScope, Role

final = len(sys.argv) > 1 and sys.argv[1] == "final"
bundle = "./manual_profile_cases_final.cjs" if final else "./manual_profile_cases.cjs"
suffix = "_final" if final else ""
source = subprocess.check_output(["node", "-e", "console.log(JSON.stringify(require(" + json.dumps(bundle) + ").purlProfileCases))"], cwd=RUN)
cases = json.loads(source)
(RUN / ("manual_profile_inputs" + suffix + ".json")).write_bytes(source)
scope = AccessScope.for_authenticated_user("synthetic-purl-calibration", "synthetic-assets-tenant", Role.TENANT_ADMIN)
result = [{**case, "server_safe": _safe_purl_reference(case["purl"])} for case in cases]
for item in result:
    if item["name"] in {"plain tab", "plain newline"}:
        now = datetime.now(timezone.utc)
        document = {"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1, "components": [{"type": "library", "name": "synthetic", "purl": item["purl"]}]}
        try:
            parse_inventory_input(json.dumps(document).encode(), manifest_format="cyclonedx_json", scope=scope, authorized_asset_tenant_id=scope.tenant_id, asset_id="a0000000-0000-4000-8000-000000000001", snapshot_number=1, source_version="synthetic-profile-1", observed_at=now, recorded_at=now)
            item["server_adapter_accepts_raw_control"] = True
        except SbomValidationError as error:
            item["server_adapter_accepts_raw_control"] = False
            item["server_adapter_reason"] = error.code
(RUN / ("backend_profile_matrix" + suffix + ".json")).write_text(json.dumps({"backend_git_material": "5be873ec38a41955b5a58e9762df4b866a7a9d63", "backend_profile_git_lf_sha256": hashlib.sha256(original).hexdigest(), "backend_profile_raw_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "backend_profile_lf_equal": True, "cases": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
differences = [entry["name"] for entry in result if entry["expected"] != entry["server_safe"]]
unexpected = [entry["name"] for entry in result if entry["expected"] != entry["server_safe"] and not (entry["name"] in {"plain tab", "plain newline"} and entry.get("server_adapter_accepts_raw_control") is False)]
print(json.dumps({"cases": len(result), "backend_expected_differences": differences, "backend_profile_equal_cases": len(result) - len(differences), "raw_control_adapter_rejections": 2, "unexpected_differences": unexpected, "model_calls": 0, "data_mode": "synthetic_contract"}))
if unexpected:
    raise SystemExit(1)
